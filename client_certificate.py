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

import sys, os, logging, shutil
import datetime
from OpenSSL import crypto
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
from cryptography import x509 as cx509
from cryptography.x509.oid import NameOID
from cicd.openssl import gen_ca, gen_csr, sign_csr, sign_server_csr, getSANValue
import uuid

class ClientCertificate:
    def __init__(self, numeric_level, params):
        logging.basicConfig(level=numeric_level, stream=sys.stdout)
        self.params = params
        if not 'container_name' in self.params:
            self.params['container_name'] = 'container' # simple string to make the naming convention consistent when no container_name is given.
        if (not 'client_crt_key' in self.params or self.params['client_crt_key'] == '') and 'container_name' in self.params:
            client_crt_key = '.' + self.params['container_name'] + "-" + self.params['uuid']
            self.params['client_crt_key'] = client_crt_key
            self.params['default_client_crt_key'] = True

        # store all cert paths
        global is_client_using_own_keys
        is_client_using_own_keys= False
        self.client_crt_key = './' + self.params['client_crt_key']
        if not 'certpath' in self.params:
            self.cert_dir = self.client_crt_key + '.d'
        else:
            split_certpath = str.split(self.params['certpath'], '/')
            certpath_dir="/".join(split_certpath[:-1])
            self.params['certpath']=certpath_dir
            self.cert_dir='./'  + self.params['certpath']
            is_client_using_own_keys=True

        # set up default file paths if not specificed through a config json file or command-line parameters
        if not 'capath' in self.params:
            self.params['capath'] = self.cert_dir + '/client-ca.pem'
        if not 'cakeypath' in self.params:
            self.params['cakeypath'] = self.cert_dir + '/client-ca-key.pem'
        if not 'certpath' in self.params:
            self.params['certpath'] = self.cert_dir + '/server-cert.pem'
        if not 'csrpath' in self.params:
            self.params['csrpath'] = self.cert_dir + '/server-csr.pem'

        if not os.path.isdir(self.cert_dir):
            pem_files = (self.params['capath'], self.params['cakeypath'], self.params['certpath'], self.params['csrpath'])
            for pem_file in pem_files:
                if self.cert_dir in pem_file:
                    try:
                        os.mkdir(self.cert_dir)
                        break
                    except Exception as e:
                        logging.error('failed to create a working directory at {} e={}'.format(self.cert_dir, e))
                        sys.exit(-1)

        if 'verbose' in self.params:
            self.verbose = int(self.params['verbose'])
        else:
            self.verbose = 0
        if 'cloud' in self.params:
            self.cloud = self.params['cloud']
        else:
            self.cloud = 0
        # logging.info('found client_crt_key={}'.format(self.params['client_crt_key']))

    def status(self):
        logging.info('status called')
        return 'OK'

    def sign_csr(self):
        capath = self.params['capath']
        cakeypath = self.params['cakeypath']
        certpath = self.params['certpath']
        csrpath = self.params['csrpath']
        sign_csr(certpath, csrpath, capath, cakeypath)

    def client_certificate(self, gen_cert=True):
        client_crt_key = self.params['client_crt_key']
        capath = self.params['capath']
        cakeypath = self.params['cakeypath']
        if os.path.exists(client_crt_key) and os.path.exists(capath) and os.path.exists(cakeypath):
            logging.info('client_certificate: using supplied pem files client_crt_key={} capath={} cakeypath={}'.format(client_crt_key, capath, cakeypath))
            gen_cert = False
        if gen_cert == False:
            cert = None
            ca = None
            end_cert = '-----END CERTIFICATE-----\n'
            if os.path.exists(client_crt_key):
                with open(client_crt_key) as f:
                    crt_key = f.read()
                (cert, key) = crt_key.split(end_cert)
                cert = cert + end_cert
            capath = self.params['capath']
            if os.path.exists(capath):
                with open(capath, 'r') as f:
                    ca = f.read()
            return cert, ca

        logging.info('client_certificate: generating client CA and certificate')
        if self.cloud:
            cert_dir = self.cert_dir
            if not os.path.isdir(cert_dir):
                try:
                    os.mkdir(cert_dir)
                except Exception as e:
                    logging.error('failed to create a working directory at {} e={}'.format(cert_dir, e))
                    sys.exit(-1)

            ca_subject = '/C=US/ST=NY/L=Armonk/O=IBM/OU=Digital Assets/CN=Client CA'
            cert_subject = '/C=US/ST=NY/L=Armonk/O=IBM/OU=Digital Assets/CN=Client'

            ca_path = cert_dir+'/client-ca.pem'
            ca_key_path = cert_dir+'/client-ca-key.pem'
            csr_path = cert_dir+'/client-csr.pem'
            cert_key_path = cert_dir+'/client-cert-key.pem'
            cert_path = cert_dir+'/client-cert.pem'

            self.exit_if_exist(ca_path, ca_key_path, csr_path, cert_key_path, cert_path)

            ca_cert, _ = gen_ca(ca_subject, ca_path, ca_key_path)
            _, cert_key = gen_csr(cert_subject, csr_path, cert_key_path)
            cert = sign_csr(cert_path, csr_path, ca_path, ca_key_path)

            ca_bytes = crypto.dump_certificate(crypto.FILETYPE_PEM, ca_cert)
            pkey_bytes = crypto.dump_privatekey(crypto.FILETYPE_PEM, cert_key)
            cert_bytes = crypto.dump_certificate(crypto.FILETYPE_PEM, cert)

            if os.path.exists('./' + client_crt_key):
                logging.fatal('exiting since a client certificate file, ./' + client_crt_key + ', already exists')
                sys.exit(-1)
            with open('./' + client_crt_key, 'w') as f:
                f.write(cert_bytes.decode('utf-8'))
                f.write(pkey_bytes.decode('utf-8'))

            with open(cert_dir+'/client-cert-bundle.pem', 'w') as f:
                f.write(cert_bytes.decode('utf-8'))
                f.write(ca_bytes.decode('utf-8'))

            return cert_bytes.decode('utf-8'), ca_bytes.decode('utf-8')

        pkey_crypto = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )
        pkey_bytes = pkey_crypto.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )

        common_name = os.uname()[1]
        name = cx509.Name([cx509.NameAttribute(NameOID.COMMON_NAME, common_name)])
        now = datetime.datetime.now(datetime.timezone.utc)
        cert_crypto = (
            cx509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(pkey_crypto.public_key())
            .serial_number(1)
            .not_valid_before(now)
            .not_valid_after(now + datetime.timedelta(days=365))
            .sign(pkey_crypto, hashes.SHA256(), backend=default_backend())
        )
        cert_bytes = cert_crypto.public_bytes(serialization.Encoding.PEM)

        if os.path.exists('./' + client_crt_key):
            logging.fatal('exiting since a client certificate file, ./' + client_crt_key + ', already exists')
            sys.exit(-1)
        with open('./' + client_crt_key, 'w') as f:
            f.write(cert_bytes.decode('utf-8'))
            f.write(pkey_bytes.decode('utf-8'))

        #print("generated cert_bytes: " + cert_bytes.decode('utf-8'))
        return cert_bytes, None

    def server_certificate(self, gen_cert=True):

        client_crt_key = self.params['client_crt_key']
        capath = self.params['capath']
        cakeypath = self.params['cakeypath']
        san = self.params['hostname']
        cert_dir = self.cert_dir
        cert_path = cert_dir+'/server-cert.pem'
        cert_key_path = cert_dir+'/server-cert-key.pem'

        san = 'DNS:'+san

        if os.path.exists(cert_path):
            san_value = getSANValue(cert_path)
            if (san != san_value):
                logging.fatal('server_certificate: Regenerating the server certificate with the SAN value provided'
                              ' in json file. In certificate san value is : '+san_value + ' and in json file: ' + san)
            else:
                gen_cert = False

        if gen_cert == False:
            server_cert = None
            if os.path.exists(cert_path):
                with open(cert_path, 'r') as f:
                    cert = f.read()
                with open(cert_key_path, 'r') as f:
                    cert_key = f.read()
            return cert, cert_key

        if not os.path.exists(client_crt_key):
                logging.error('Create the directory, CA certificate and client certificate first. Then retry to create server certificate.')
                sys.exit(-1)


        if os.path.exists(client_crt_key) and os.path.exists(capath) and os.path.exists(cakeypath):
            logging.info('server_certificate: using supplied pem files cert_directory={} capath={} cakeypath={}'.format(client_crt_key, capath, cakeypath))
            
        logging.info('server_certificate: Generating server certificate')

        if self.cloud:
            cert_dir = self.cert_dir
            if not os.path.isdir(cert_dir):
                try:
                    os.mkdir(cert_dir)
                except Exception as e:
                    logging.error('failed to create a working directory at {} e={}'.format(cert_dir, e))
                    sys.exit(-1)

        cert_subject = '/C=US/ST=NY/L=Armonk/O=IBM/OU=Digital Assets/CN=Server'
        csr_path = cert_dir+'/server-csr.pem'
        cert_key_path = cert_dir+'/server-cert-key.pem'
        cert_path = cert_dir+'/server-cert.pem'
        san_list = list(san.split(", "))

        _, cert_key = gen_csr(cert_subject, csr_path, cert_key_path)
        logging.info('server_certificate: Successfully generated server CSR')

        cert = sign_server_csr(cert_path, csr_path, capath, cakeypath, san_list)
        logging.info('server_certificate: Successfully generated server certificate')

        cert_bytes = crypto.dump_certificate(crypto.FILETYPE_PEM, cert)
        return cert_bytes, cert_key_path


    def exit_if_exist(self, *files):
        existing_files = []
        for file in files:
            if os.path.isfile(file):
                existing_files.append(file)
        if len(existing_files) > 0:
            logging.error('client_certificate: exiting because the following files already exist - {}'.format(' '.join(existing_files)))
            logging.error('client_certificate: specify CLIENT_CRT_KEY, CAPATH, and CAKEYPATH or empty the directory')

            sys.exit(-1)

    def delete_certificates(self):
        if 'client_crt_key' in self.params and 'default_client_crt_key' in self.params and self.params['default_client_crt_key']:
            client_crt_key = self.params['client_crt_key']
            client_crt_path = './' + client_crt_key
            if os.path.exists(client_crt_path):
                os.remove(client_crt_path)
                if self.verbose > 0:
                    logging.info('client_crt ' + client_crt_path + ' has been deleted')
            else:
                if self.verbose > 0:
                    logging.info('client_crt ' + client_crt_path + ' did not exist')
            client_crt_dir = client_crt_path + '.d'
            if os.path.isdir(client_crt_dir):
                shutil.rmtree(client_crt_dir)

