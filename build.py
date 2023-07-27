#!/usr/bin/env python3
#
# Licensed Materials - Property of IBM
#
# 5737-I09
#
# Copyright IBM Corp. 2019 All Rights Reserved.
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp
#
import sys, os, base64, re, tarfile, json, platform, argparse, binascii, shutil, logging
from datetime import datetime, timezone
import time
from subprocess import check_output
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric import utils
from cryptography.exceptions import InvalidSignature
from filters import JsonFilter, StringFilter
import requests
from cicd.openssl import gen_ca, gen_csr
import client_certificate
import config_cipher
import uuid
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

default_parameter_file = './env.json'
internal_params = {}
header = " -H \'Content-Type: application/json\'"
header_plain = " -H \'Content-Type: text/plain\'"

logger = logging.getLogger(__name__)

# These are the parameter names of the required parameters
# TODO: check if we need REPO_ID
parameter_names = {'RUNTIME_TYPE','DOCKER_REPO', 'DOCKER_USER', 'DOCKER_PASSWORD', 'GITHUB_URL', 'SECRET', 'IMAGE_TAG'}
manifest_parameters = {'MANIFEST_BUCKET_NAME',
                       'MANIFEST_COS_API_KEY_ID',
                       'MANIFEST_COS_RESOURCE_CRN',
                       'MANIFEST_COS_AUTH_ENDPOINT',
                       'MANIFEST_COS_ENDPOINT'}
state_parameters = {'STATE_BUCKET_NAME',
                    'STATE_COS_API_KEY_ID',
                    'STATE_COS_RESOURCE_CRN',
                    'STATE_COS_AUTH_ENDPOINT',
                    'STATE_COS_ENDPOINT'}
other_optional_parameters = {'SECRETS',
                             'NEW_SECRET',
                             'BUILD_SCRIPT',
                             'BUILD_DIR',
                             'ARG',
                             'GITHUB_BRANCH', 'IMAGE_TAG_PREFIX',
                             'GITHUB_RECURSE_SUBMODULES',
                             'DOCKER_BASE_USER', 'DOCKER_BASE_PASSWORD',
                             'DOCKER_RO_USER', 'DOCKER_RO_PASSWORD',
                             'DOCKER_BASE_SERVER',
                             'DOCKER_PUSH_SERVER',
                             'DOCKER_CONTENT_TRUST_BASE',
                             'DOCKER_CONTENT_TRUST_BASE_SERVER',
                             'DOCKER_CONTENT_TRUST_PUSH_SERVER',
                             'ICR_BASE_REPO',
                             'ICR_BASE_REPO_PUBLIC_KEY',
                             'DOCKERFILE_PATH',
                             'DOCKER_BUILD_PATH',
                             'ISV_SECRET',
                             'ENV_WHITELIST',
                             'EXIT_NONZERO'}
additional_env_vars = {'RUNQ_ROOTDISK',
                       'RUNQ_RUNQENV',
                       'RUNQ_SYSTEMD',
                       'IMAGE_TAG',
                       'REGION',
                       'PHASE',
                       'LPAR_NAME',
                       'CPC',
                       'RUNQ_CPU',
                       'RUNQ_MEM',
                       'POD'}
skip_list = {'registration_file'}


class Build:
    def __init__(self, args, internal_params):
        numeric_level = getattr(logging, args.loglevel.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError('Invalid log level: %s' % numeric_level)
        logging.basicConfig(level=numeric_level, stream=sys.stdout)
        json_keys = {'ADMIN_PASSWORD', 'ROOT_SSH_KEY', 'CLIENT_CRT',
                     'DOCKER_BASE_PASSWORD', 'DOCKER_PASSWORD', 'DOCKER_RO_PASSWORD',
                     'GITHUB_KEY', 'MANIFEST_COS_API_KEY_ID', 'MANIFEST_COS_RESOURCE_CRN',
                     'BACKUP_COS_API_KEY_ID', 'BACKUP_COS_RESOURCE_CRN',
                     'COS_API_KEY_ID', 'COS_RESOURCE_CRN',
                     'CONTAINER_PUBLIC_KEY', 'CONTAINER_PRIVATE_KEY',
                     'APIKEY', 'RESOURCE_INSTANCE_ID', 'SESSION_KEY', 'TOKEN', 'SECRET', 'NEW_SECRET'
                     }
        filter = JsonFilter(json_keys)
        logger.addFilter(filter)
     
        self.params = internal_params
        self.verbose = args.verbose

        if args.config_json_file != None:
            self.parameter_file = os.path.expanduser(args.config_json_file)
            if not os.path.isfile(self.parameter_file):
                logger.warning('parameter file ' + self.parameter_file + ' is not found')
                sys.exit(-1)
        elif os.path.isfile(default_parameter_file):
            if args.verbose > 1:
                if args.config_json_file == None:
                    logger.warning('A --env option was not specified, using a default file: ' + default_parameter_file)
                else:
                    logger.warning(
                        'A parameter file, ' + args.config_json_file + ', does not exist, using a default file: ' + default_parameter_file)
            self.parameter_file = default_parameter_file
        else:
            self.parameter_file = ''

        if self.parameter_file != '':
            from collections import OrderedDict
            if not os.path.exists(self.parameter_file):
                logger.warning('parameter file ' + self.parameter_file + ' is not found')
            try:
                with open(os.path.expanduser(self.parameter_file)) as f:
                    params = json.load(f, object_pairs_hook=OrderedDict)
            except json.JSONDecodeError as e: # (msg, doc, pos)
                logger.error('failed parsing json parameter file {} e={}'.format(self.parameter_file, e))
                sys.exit(-1)
            except Exception as e:
                logger.error('failed reading json parameter file {} e={}'.format(self.parameter_file, e))
                sys.exit(-1)

            if args.verbose > 1:
                logger.info("parameter_file:" + self.parameter_file)
            updateparamfile = False
            if not 'RUNTIME_TYPE' in params:
                params['RUNTIME_TYPE'] = "vpc"
                updateparamfile = True
            if not 'UUID' in params:
                params['UUID'] = str(uuid.uuid4())
                updateparamfile = True
            if not 'SECRET' in params:
                if args.verbose > 1:
                    logger.info('generating a new secret')
                params['SECRET'] = base64.b64encode(os.urandom(128)).decode('UTF-8')
                updateparamfile = True
            if updateparamfile:
                self.update_param_file(params)
            for key in params.keys():
                if not key.lower() in skip_list:
                    self.params[key.lower()] = params[key]
            # if self.verbose > 0:
            #    logger.info('__init_:params=' + json.dumps(self.params, indent=4, sort_keys=True))

        for name in vars(args).keys():
            if vars(args)[name]:
                self.params[name.lower()] = str(vars(args)[name])

        self.client_certificate = client_certificate.ClientCertificate(numeric_level, self.params)
        if not 'client_crt_key' in self.params:
            logging.fatal('build.py init: undefined client_crt_key')
            sys.exit(-1)
        self.client_crt_key = './' + self.params['client_crt_key']
        if not 'capath' in self.params:
            logging.fatal('build.py init: undefined capath')
            sys.exit(-1)
        self.client_ca = './' + self.params['capath']

        if not 'manifest_cos_api_key_id' in self.params and 'cos_api_key_id' in self.params:
            self.params['manifest_cos_api_key_id'] = self.params['cos_api_key_id']
        if not 'manifest_cos_resource_crn' in self.params and 'cos_resource_crn' in self.params:
            self.params['manifest_cos_resource_crn'] = self.params['cos_resource_crn']
        if not 'manifest_cos_endpoint' in self.params and 'cos_endpoint' in self.params:
            self.params['manifest_cos_endpoint'] = self.params['cos_endpoint']
        if not 'manifest_cos_auth_endpoint' in self.params and 'cos_auth_endpoint' in self.params:
            self.params['manifest_cos_auth_endpoint'] = self.params['cos_auth_endpoint']

        if not 'state_cos_api_key_id' in self.params and 'cos_api_key_id' in self.params:
            self.params['state_cos_api_key_id'] = self.params['cos_api_key_id']
        if not 'state_cos_resource_crn' in self.params and 'cos_resource_crn' in self.params:
            self.params['state_cos_resource_crn'] = self.params['cos_resource_crn']
        if not 'state_cos_endpoint' in self.params and 'cos_endpoint' in self.params:
            self.params['state_cos_endpoint'] = self.params['cos_endpoint']
        if not 'state_cos_auth_endpoint' in self.params and 'cos_auth_endpoint' in self.params:
            self.params['state_cos_auth_endpoint'] = self.params['cos_auth_endpoint']

        if 'ssc_host' in self.params:
            self.ssc_host = self.params['ssc_host']
        else:
            self.ssc_host = None

        if 'hostname' in self.params:
            self.hostname = self.params['hostname']
        else:
            self.hostname = None
            logger.fatal('HOSTNAME is not configured. Please configure HOSTNAME to generate certificates and to'
                         ' communicate with secure build server.')
            sys.exit(-1)

        if 'cicd_port' in self.params:
            self.cicd_port = self.params['cicd_port']
        else:
            self.cicd_port = '443'

        stringstobemasked = []
        for key in json_keys:
            if key.lower() in self.params:
                stringstobemasked.append(self.params[key.lower()])
        filter = StringFilter(stringstobemasked)
        logger.addFilter(filter)

        if args.verbose > 0:
            logger.info('__init__:params=' + json.dumps(self.params, indent=4, sort_keys=True))

        # self.cos = Cos(self.params)

    def create_runtimetype_file(self):
        # storing the runtime_type as a file
        if client_certificate.is_client_using_own_keys == False:
            path = self.client_crt_key + '.d'
        else:
            path = self.params['certpath']

        filename = "sbsRuntime_Type"
        with open(os.path.join(path, filename), 'w') as fp:
            fp.write(self.params['runtime_type'])
    
    def cicd_socket_address(self):
        cicd_host = self.ssc_host

        if self.hostname != None:
            cicd_host = self.hostname

        return cicd_host + ":" + self.cicd_port

    def parameters(self, update={}):
        self.params.update(update)
        return self.params

    def more_verbose(self, delta=1):
        self.verbose = self.verbose + delta

    def less_verbose(self, delta=1):
        self.verbose = self.verbose - delta

    def request_api(self, api, request, uri, noverify=False, params=None, json_data='', json_response=True,
                    ignore_connection_error=False):
        try:
            resp = request('https://' + self.cicd_socket_address() + uri, params=params, json=json_data,
                           cert=self.client_crt_key, verify=False if noverify else self.client_ca)
        except requests.exceptions.SSLError as e:
            logger.info('build: {} SSLError [upload a signed server certificate to SBS if you haven\'t]'.format(api))
            logger.debug('build: {} SSLError e={}'.format(api, e))
            return '', -1
        except requests.exceptions.ConnectionError as e:
            if not ignore_connection_error or self.verbose > 0:
                logger.info('build: {} NewConnectionError e={}'.format(api, e))
            return '', -1
        except Exception as e:
            logger.info('build: {} e={}'.format(api, e))
            return '', -1
        try:
            json_resp = json.loads(resp.content)
            if self.verbose > 0:
                logger.info(api + ': response=' + json.dumps(json_resp, indent=4))
            return json_resp, resp.status_code
        except Exception as e:
            if resp.content == '':
                if self.verbose > 0:
                    logger.info(api + ': response=None')
            elif json_response == True:
                logger.info('{}: response={} [exception]={}'.format(api, resp.text, e))
            elif self.verbose > -1:
                logger.info(api + ': response=' + resp.text)
            return resp.content, resp.status_code

    def init(self, update=False):
        body = {}
        if 'github_key_file' in self.params and self.params['github_key_file'] != '':
            body["GITHUB_KEY"] = self.read_key(self.params['github_key_file'])
        else:
            body["GITHUB_KEY"] = ""

        
        if 'icr_base_repo_public_key' in self.params and self.params['icr_base_repo_public_key'] != '':
            body["BASE_REPO_PUBLIC_KEY"] = self.read_key(self.params['icr_base_repo_public_key'])
        else:
            body["BASE_REPO_PUBLIC_KEY"] = ""

        if 'new_secret' in self.params and update:
            if not 'secret' in self.params:
                logger.error('init/update: SECRET has not been defined')
                sys.exit(-1)
            if self.verbose > 1:
                logger.info('renewing a secret')
            self.params['new_secret'] = base64.b64encode(os.urandom(128)).decode('UTF-8')
      
        if self.params['runtime_type'] != '' and update:
            # Creating runtime_type file if it does not exist
            if client_certificate.is_client_using_own_keys == False:
                path = self.client_crt_key + '.d'
                runtime_type_file = path + '/' + 'sbsRuntime_Type'
            else:
                path = self.params['certpath']
                runtime_type_file = path + '/' + 'sbsRuntime_Type'
            if not os.path.exists(runtime_type_file):
                build.create_runtimetype_file()
            
            else:
                with open(os.path.join(path, 'sbsRuntime_Type'), 'r') as fp:
                    runtime_content = fp.read()

                if self.params['runtime_type'] != runtime_content:
                    logger.error("Update is not supported for RUNTIME_TYPE")
                    sys.exit(-1)
        
        for name in parameter_names:
            if name.lower() in self.params:
                # IMAGE_TAG is the one for a secure build service image
                # Secure build service stores this as 'BUILD_IMAGE_TAG'
                value = self.params[name.lower()]
                if name == 'IMAGE_TAG':
                    name = 'BUILD_' + name
                body[name] = value
                if name == 'RUNTIME_TYPE':
                   if value == "vpc" and 'repo_id' in self.params:
                    logger.fatal("REPO_ID is not supported parameter in vpc")
                    sys.exit(-1)
                   elif value =="on-prem" and 'repo_id' in self.params:
                    logger.fatal("REPO_ID is not supported parameter in on-prem")
                    sys.exit(-1)
                   elif value =="classic" and 'repo_id' not in self.params:
                    logger.fatal('undefined parameter REPO_ID')
                    sys.exit(-1)
                   elif value =="classic" and 'repo_id' in self.params:
                    body['REPO_ID'] = self.params['repo_id']
                   else:
                    body[name] = value
            else:
                logger.fatal('undefined parameter ' + name)
                sys.exit(-1)

        # storing the runtime_type as a file
        build.create_runtimetype_file()

        for parameters in (manifest_parameters, state_parameters, other_optional_parameters):
            for name in parameters:
                if name.lower() in self.params:
                    body[name] = self.params[name.lower()]

        # request = " -d \'" + json.dumps(body, sort_keys=True) + "\'"
        if self.verbose > 1:
            logger.info("init:params=" + json.dumps(self.params, indent=4, sort_keys=True))
            logger.info("init:request=" + json.dumps(body, indent=4, sort_keys=True))

        if update:
            request_verbe = requests.patch
            api = 'update'
        else:
            request_verbe = requests.post
            api = 'init'

        resp, status_code = self.request_api(api, request_verbe, '/image', json_data=body)

        # update secret only when the update was successful
        if 'new_secret' in self.params and update and 'status' in resp and resp['status'] == 'OK':
            from collections import OrderedDict
            param_file = os.path.expanduser(self.parameter_file)
            with open(param_file) as f:
                params = json.load(f, object_pairs_hook=OrderedDict)
            params['SECRET'] = self.params['new_secret']
            self.params.pop('new_secret')
            self.update_param_file(params)

        return resp

    def build(self):
        resp, status_code = self.request_api('build', requests.put, '/image')
        return resp

    def clean(self):
        resp, status_code = self.request_api('clean', requests.delete, '/image')
        return resp

    def status(self, noverify=False, ignore_connection_error=False):
        resp, status_code = self.request_api('status', requests.get, '/image', noverify=noverify, ignore_connection_error=ignore_connection_error)
        return resp

    def create_client_cert(self):
        self.client_certificate.client_certificate(gen_cert=True)

    def create_server_cert(self):
        self.client_certificate.server_certificate(gen_cert=True)

    def delete_certificates(self):
        self.client_certificate.delete_certificates()

    def get_state_image(self):
        body = {}
        if 'state_bucket_name' in self.params:
            body['state_bucket_name'] = self.params['state_bucket_name']
        resp, status_code = self.request_api('get-state-image', requests.get, '/state-image', json_data=body)
        if not 'name' in resp or not 'export_tag' in resp or (not 'state_bucket_name' in body and not 'state' in resp):
            logger.error('unexpected response={}'.format(json.dumps(resp, indent=4)))
            return ''
        state_name = resp["name"]
        logger.info("state:name: {}".format(state_name))
        with open(state_name, 'w') as f:
            f.write(json.dumps(resp))
        return resp

    def post_state_image(self):
        body = {}
        if not 'secret' in self.params:
            logger.error('missing secret')
            return ''
        body['secret'] = self.params['secret']

        if 'state_image' in self.params and 'state_bucket_name' in self.params:
           if 'name' in self.params:
            logger.error('When cloud object storage(COS) is enabled, state-image parameter is not required')
            return ''
           else:
            logger.error('When cloud object storage(COS) is enabled, name parameter is required')
            return ''

        if 'state_image' in self.params:
            with open(self.params['state_image']) as f:
                state_image = json.load(f)
            if not 'name' in state_image or not 'state' in state_image:
                logger.error('unexpected image file {}'.format(str(state_image)))
                return ''
            logger.info('state:name: {}'.format(state_image['name']))
            body['state'] = state_image['state']
        elif 'state_bucket_name' in self.params:
            body['state_bucket_name'] = self.params['state_bucket_name']
            if not 'name' in self.params:
                logger.error('When cloud object storage(COS) is enabled, name parameter is required')
                return ''
            body['name'] = self.params['name']

        resp, status_code = self.request_api('post-state-image', requests.post, '/state-image', json_data=body)
        return resp
    
    def log(self, logname):
        self.less_verbose()
        resp, status_code = self.request_api('log', requests.get, '/log/'+logname, json_response=True)
        self.more_verbose()
        if not 'log' in resp:
            logger.error('failed to obtain log response={}'.format(json.dumps(resp, indent=4)))
            return resp
        for line in resp['log'].split('\n'):
            logger.info(line)

    def config_python(self):
        if self.params['runtime_type'] == 'classic':
            self.less_verbose(delta=2)
            resp, status_code = self.request_api(
                'get-config-python', requests.get, '/config-python', json_response=False)
            self.more_verbose(delta=2)

            if status_code != 201:
                logger.error(resp.decode('utf-8'))
                return

            repo_regfile_name = 'repo_regfile'
            if 'repo_id' in self.params and self.params['repo_id'] != '':
                repo_regfile_name = self.params['repo_id']

            with open(repo_regfile_name + '.py', 'w') as f:
                f.write(resp.decode('utf-8'))

            logger.info('a python config file has been written to {}.'.format(
                repo_regfile_name+'.py'))
        else:
            if self.params['runtime_type'] == 'on-prem':
                logger.fatal("get-config-python is not supported for on-prem")
            else:
                logger.fatal("get-config-python is not supported for vpc")
            sys.exit(-1)
    
    def config_json(self):
        if self.params['runtime_type'] == 'classic':
            self.less_verbose(delta=2)
            resp, status_code = self.request_api('get-config-json', requests.get, '/config-json', json_response=True)
            self.more_verbose(delta=2)

            if status_code != 201:
                if status_code != -1:
                    logger.error(resp.decode('utf-8'))
                return

            if self.verbose > 1:
                logger.info('config_json={}'.format(json.dumps(resp, indent=4)))
            repo_regfile_name = 'repo_regfile'
            if 'repo_id' in self.params and self.params['repo_id'] != '':
                repo_regfile_name = self.params['repo_id']


            config = resp
            if not 'cap_add' in config or not 'ALL' in config['cap_add']:
                config['cap_add'] = ['ALL']
            for env_var in additional_env_vars:
                if not 'envs_whitelist' in config:
                    config['envs_whitelist'] = []
                if not env_var in config['envs_whitelist']:
                    config['envs_whitelist'].append(env_var)

    #to add IV secret to .enc file if isv flag is set
            if args.isv_secrets:
                if 'isv_secret' in self.params and len(self.params['isv_secret'])!=0:
                    isv=self.params['isv_secret']
                    isv_secrets={}
                    key_value_pair={}
                    for key,value in isv.items():
                        if (len(key) != 0 and len(value) != 0):
                            key_value_pair.update({key:value})
                            isv_secrets.update(key_value_pair)
                        else:
                            if (len(key) == 0 or len(value) == 0):
                                logger.fatal('Provide valid values of secrets in form of key and value pair')
                                sys.exit(-1)

                    secrets_json = {'secrets':{'mount_path': '/isv_secrets/secrets.json', 'secrets_list': isv_secrets}}
                    config.update(secrets_json)
                   
                else:
                    logger.fatal('No values are provided under ISV_SECRET')
                    sys.exit(-1)
       
            cc = config_cipher.ConfigCipher(args.loglevel)
            email = self.params['email'] if 'email' in self.params else ''
            keyid = self.params['key_id'] if 'key_id' in self.params else 'secure-build'
            encrypted_config_json = cc.encrypt_config_json(config, email=email, keyid=keyid)
            if encrypted_config_json == None:
                logger.error('an encrypted json config file was not written.')
                return

            with open(repo_regfile_name+'.enc', 'w') as f:
                f.write(encrypted_config_json)

            logger.info('a json config file has been written to {}.'.format(repo_regfile_name+'.enc'))
        else:
            if self.params['runtime_type'] == 'on-prem':
                logger.fatal("get-config-json is not supported for on-prem")
            else:
                logger.fatal("get-config-json is not supported for vpc")
            sys.exit(-1)

    def instance_env(self):
        env_vars = {}
        if 'root_ssh_key_file' in self.params:
            with open(os.path.expanduser(self.params['root_ssh_key_file'])) as f:
                root_ssh_key = base64.b64encode(f.read().encode('utf-8')).decode('utf-8')
            env_vars['ROOT_SSH_KEY'] = root_ssh_key
        cert, ca = self.client_certificate.client_certificate(gen_cert=False)
        server_cert, server_key = self.client_certificate.server_certificate(gen_cert=False)
        cc = config_cipher.ConfigCipher(args.loglevel)
        #Importing the public key.
        fingerprint = cc.import_hpvs_public_key()
        ascii_value_server_key = cc.encrypt_env_variables(server_key)
        #Encoding the public key.
        env_vars['CLIENT_CRT'] = base64.b64encode(cert.encode('utf-8')).decode('utf-8')
        env_vars['CLIENT_CA'] = base64.b64encode(ca.encode('utf-8')).decode('utf-8')
        env_vars['SERVER_CRT'] = base64.b64encode(server_cert.encode('utf-8')).decode('utf-8')
        env_vars['SERVER_KEY'] = base64.b64encode(ascii_value_server_key.encode('utf-8')).decode('utf-8')
        if self.params['runtime_type'] == 'classic':
            env = ' '.join(['-e '+key+'='+value for key, value in env_vars.items()])
            logger.info('\n\n ****** Copy below environment variables and use in instance-create command. ****** \n\n')
            print(env)
        else:
            env = ''.join([key+': "'+value + '"\n' for key, value in env_vars.items()])
            logger.info('\n\n ****** Copy below environment variables and use in env contract as environment variables. ****** \n\n')
            print(env)
        return env

        logger.info('a json config file has been written to {}.'.format(repo_regfile_name + '.json'))

    def verify_manifest(self, manifest_name, public_key_pem, test):
        # if self.verbose > 0:
        logger.info('verify_manifest: manifest_name=' + manifest_name + ' test=' + str(test))
        with tarfile.open(manifest_name + '.sig.tbz', 'r:bz2') as f:
            f.extractall('./')

        # test the signature verification by adding a fake file
        if test:
            if self.verbose > 0:
                logger.info('verify_test')
            test_dir = './verify_test'
            os.mkdir(test_dir)
            os.chdir(test_dir)
            with tarfile.open('../' + manifest_name + '.tbz', 'r:bz2') as f:
                f.extractall('.')
            with open('git/fake', 'w') as f:
                f.write('fake')
            with tarfile.open('../' + manifest_name + '.tbz', 'w:bz2') as f:
                f.add('git')
            os.chdir('..')
            shutil.rmtree(test_dir)

        sig_file = manifest_name + '.sig'
        with open(sig_file, 'r') as f:
            sig_hex = f.read()

        signature = binascii.unhexlify(sig_hex)

        tar_file = manifest_name + '.tbz'

        chosen_hash = hashes.SHA256()
        hash = hashes.Hash(chosen_hash, backend=default_backend())
        with open(tar_file, 'rb') as f:
            while True:
                chunk = f.read(2048 * 64)
                if len(chunk) == 0:
                    break
                hash.update(chunk)
        digest = hash.finalize()
        if self.verbose > 0:
            logger.info("digest=" + digest.hex())

        public_key = serialization.load_pem_public_key(
            public_key_pem.encode('utf-8'),
            backend=default_backend())

        try:
            public_key.verify(signature,
                              digest,
                              # padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                              #            salt_length=padding.PSS.MAX_LENGTH),
                              # utils.Prehashed(chosen_hash)
                              padding.PKCS1v15(),
                              hashes.SHA256())
        except InvalidSignature as e:
            logger.error("Invalid Signature: {}".format(e))
            if test:
                logger.info("verify=intentionally failed")
            else:
                logger.error("verify=uintentionally failed")
            return False

        logger.info("verify=OK")

        return True

    def get_manifest(self):
        resp, status_code = self.request_api('get-manifest', requests.get, '/manifest', json_data={'BUILD_NAME':self.params['build_name']} if 'build_name' in self.params else '')
        if not 'manifest_name' in resp:
            logger.fatal("get-manifest response=" + json.dumps(resp, indent=4))
            sys.exit(-1)
        manifest_name = resp['manifest_name']
        logger.info('get-manifest manifest_name: ' + manifest_name)
        manifest_content = base64.b64decode(resp['encoded_manifest'])
        manifest_path = './' + manifest_name + '.sig.tbz'
        with open(manifest_path, 'wb') as f:
            f.write(manifest_content)
        return manifest_name

    def get_publickey(self):
        resp, status_code = self.request_api('get-publickey', requests.get, '/publickey', json_data={'BUILD_NAME':self.params['build_name']} if 'build_name' in self.params else '')
        if not 'public_key_pem' in resp:
            logger.fatal("get-publickey response=" + json.dumps(resp, indent=4))
            sys.exit(-1)
        public_key_pem = resp['public_key_pem']
        build_name = resp['build_name']
        if self.verbose > 0:
            logger.info("get-publickey: public_key_pem=" + public_key_pem)
            logger.info("get-publickey: build_name=" + build_name)
        public_key_file = 'manifest.' + build_name + '-public.pem'
        with open(public_key_file, 'w') as f:
            f.write(public_key_pem)
        return public_key_pem

    def get_signed_image_publickey(self):
        resp, status_code = self.request_api('get-config-json', requests.get, '/config-json', json_response=True)

        if status_code != 201:
            if status_code != -1:
                logger.error(resp.decode('utf-8'))
            return

        if not 'public_key' in resp:
            logger.fatal("get-signed-image-publickey response=" + json.dumps(resp, indent=4))
            sys.exit(-1)

        signed_image_public_key = resp['public_key']
        repo_name = resp['repository_name'].replace("/","-")
        if self.verbose > 0:
            logger.info("get-signed-image-publickey response=" + signed_image_public_key)
        signed_image_public_key_file = repo_name + '-public.key'
        with open(signed_image_public_key_file, 'w') as f:
            f.write(signed_image_public_key)
        logger.info("Downloaded signed image public key to file " + signed_image_public_key_file)
        return signed_image_public_key

    def get_digest(self):
        self.less_verbose(delta=2)
        resp, status_code = self.request_api(
            'get-digest', requests.get, '/imagedigest', json_response=True)
        self.more_verbose(delta=2)

        if status_code != 201:
            logger.error(resp.decode('utf-8'))
            return

        if self.verbose > 1:
            logger.info('image_digest={}'.format(json.dumps(resp, indent=4)))

        print('Digest value of the built image:', str(resp))

    def read_key(self, key_file):
        with open(os.path.expanduser(key_file), 'r') as f:
            data = f.read()  # .replace('\n', '\\n')
        if self.verbose > 1:
            logger.info("key=" + data)
        return data

    def update_param_file(self, new_params):
        param_file = os.path.expanduser(self.parameter_file)
        if os.path.isfile(param_file):
            timestamp = datetime.fromtimestamp(time.time(), timezone.utc).strftime('%Y-%m-%d_%H-%M-%S.%f')
            backup_file = param_file + '.' + timestamp
            try:
                os.rename(param_file, backup_file)
                logger.info('parameter file {} renamed to {}'.format(param_file, backup_file))
            except Exception as e:
                logger.fatal('cannot rename parameter file {} error={}'.format(param_file, e))
                sys.exit(-1)
        else:
            logger.warning('parameter file {} not found'.format(param_file))
        with open(param_file, 'w') as f:
            json.dump(new_params, f, indent=4)


if __name__ == '__main__':

    parser = argparse.ArgumentParser(prog='build.py')
    parser.add_argument("--env", dest='config_json_file', help="json file to set environment parameters (default: env.json)", required= True)
    parser.add_argument("-v", "--verbose", action="count", default=0, help="increase verbosity")
    parser.add_argument("--version", action="version", version="%(prog)s v0.221", help="show version")
    parser.add_argument("command", help="[init|update|build|clean|status|log|get-config-json|get-config-python|get-manifest|get-publickey|get-signed-image-publickey|get-digest|get-state-image|post-state-image|create-client-cert|create-server-cert|delete-certificates|instance-env]")
    parser.add_argument("--github-key-file", help="github_key_file")
    parser.add_argument("--log", help="log_name e.g. build")
    parser.add_argument("--loglevel", default='INFO', help=argparse.SUPPRESS)
    parser.add_argument("--verify-manifest", action="count", default=0, help="verify manifest")
    parser.add_argument("--verify-test", action="count", default=0, help="test manifest verification")
    parser.add_argument("--client-crt-key", help="a certificate file for client authentication")
    parser.add_argument("--build-name", help="specify a non-latest build_name for manifest operations (get-manifest, and get-publickey)")
    parser.add_argument("--container-name", help="CICD container name")
    parser.add_argument("--new-secret", action="count", default=0, help="update secret")
    parser.add_argument("--state-image", help="encrypted state image file")
    parser.add_argument("--secret", help="secret")
    parser.add_argument("--noverify", action="count", help="skip verifying server certificate")
    parser.add_argument("--capath", help="path name of a certificate authority pem file to sign server csr")
    parser.add_argument("--cakeypath", help="path name of certificate authority key pem file to sign server csr")
    parser.add_argument("--csrpath", help="path name of server csr pem file")
    parser.add_argument("--certpath", help="path name of signed server certificate pem file")
    parser.add_argument("--cloud", action='count', default=1, help='cloud mode')
    parser.add_argument("--state-bucket-name", help='state bucket name')
    parser.add_argument("--name", help='name of state image')
    parser.add_argument("--config-json-path", help="clear text config json file")
    parser.add_argument("--rd-path", help="encrypted registration file")
    parser.add_argument("--key-id", help="vendor key id")
    parser.add_argument("--email", help="vendor key user email")
    parser.add_argument("--isv-secrets",action="count", default=False, help="If --isvsecret flag is true, isv secrets will be set to registration file. By default flag is false so no isv secrets will be set.")
    args = parser.parse_args()

    if args.verbose > 1:
        for name in vars(args).keys():
            if vars(args)[name]:
                logger.info(name + " " + str(vars(args)[name]))

    build = Build(args, {})

    command = args.command

    if command == "init":
        build.more_verbose()
        build.init(update=False)
    elif command == "update":
        build.more_verbose()
        build.init(update=True)
    elif command == "build":
        build.more_verbose()
        build.build()
    elif command == "clean":
        build.more_verbose()
        build.clean()
    elif command == "status":
        build.more_verbose()
        build.status(noverify=args.noverify)
    elif command == "log":
        build.more_verbose()
        build.log(args.log)
    elif command == "get-config-python":
        build.more_verbose()
        build.config_python()
    elif command == "get-config-json":
        build.more_verbose()
        build.config_json()
    elif command == "get-manifest":
        manifest_name = build.get_manifest()
        if args.verify_manifest:
            public_key_pem = build.get_publickey()
            build.verify_manifest(manifest_name, public_key_pem, args.verify_test)
    elif command == "get-publickey":
        build.get_publickey()
    elif command == "get-signed-image-publickey":
        build.get_signed_image_publickey()
    elif command == "get-digest":
        build.get_digest()
    elif command == "get-state-image":
        build.get_state_image()
    elif command == "post-state-image":
        build.more_verbose()
        build.post_state_image()
    elif command == "create-client-cert":
        build.more_verbose()
        build.create_client_cert()
    elif command == "create-server-cert":
        build.more_verbose()
        build.create_server_cert()
    elif command == "delete-certificates":
        build.more_verbose()
        build.delete_certificates()
    elif command == 'instance-env':
        build.instance_env()
    else:
        logger.fatal("unknown command: " + command)
        