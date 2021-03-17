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
import gnupg, json, logging, argparse, sys, os, re
from filters import JsonFilter

ha_public_key = """
-----BEGIN PGP PUBLIC KEY BLOCK-----

mQINBF5q0TYBEACx5qWOp9JuiK7qKInYuBiqQp8Ac29e27XqGRtlk5UWbK0XP4wz
zm6chk2LM1pKx5jY0MbQc7DO8QWQE2W/6EAFqi/1T/iWWddE4sv9q29usFeL7d5t
cXk4oBorT/gdl3KiAlXuYUa111opdElmPUam6GyMXc9eZEZ+0rFno4RJO+lSp8CX
l4ejnsdl+NFt7eYmECd9Zq0ADdV2wNZvrA7vj0faAlSqVvXqMCkAosF5HqNTY5vs
rMwL3SRagPHOCjg/Tx5K1nugTh+W6nH4c2P52X3a06q7jCZ9JkGb5ZudVCwmZNI1
4NhPkp9rNUCPEUS+hOL5C2ZBok5rwr59tXkZEnHT5gRdpSD4htLiCQVys+lUHkFu
STrLihgGaFXYtAT3N6q/0EM5tBX4kwTsDuRefW71Kxa0X/f6s3dpyTALdZox504U
BeA9AtZi43cp48uDEIVGUC5moP2Z5hL/yANFRCQNFeWy52ghhsUGdL2lBKvqFbzp
AqtoJGA9+1ymolVQXYrBNmFcAdHYa06W3det2q9fhF2nBdI4AbrOg4T0huebNTBn
qurf6+PZLF+NmCzE1jlqSrnsionuhBJn2Myb1O+u0IfifLmvPYXgpRG49OjfNNI2
i3sdBThhb3a3aaEEKmMQn5C3mUyYYwFJ8cQqj56/uzv7AsxZ1rneBgZvowARAQAB
tBBydG9hX2Rlc3RpbmF0aW9uiQIxBBMBCgAbBQJeatE2AhsDAgsJAhUKBRYCAwEA
Ah4BAheAAAoJEBkOqQpczdT1ef4P+wRqr83AaeRW6ckjdaeSA2YgAG1/aUydpOAK
z/iQv7jjlcdP+/IcRvpSX6C7/G/+/4WLyG3EMHnDqwBCzvvTASbvVexY2HcKqt69
rTBv8757rWTiz0TE/IoNsjHPwqiSBWEHzc5/Mdy5Ihwy5kISEnHSttltPMHi4cb2
P+Iq+wzz72jjJT81oQ8mp+cKpBPPaGRLB2BciBpY4ZuOz6P/s/30D4Y1W7rSU8Nw
JlpKUndhqp0hokpNgsA5mPERwJIj8LS+qs3dCyM0YL0A8uas5YPJw3Cc2CBkROuz
JIci7P33+dbg7cZDMh00eiEeh5jXrr5YgywiQP6oVA/nlJ0p4G+Rta8fQJz/TeDy
olt+akBXyWSRZV8XJoviqltDu7lQ4zyupDI9NvVKe7VKwqvWypXJ1d0bbkS/W88i
XplsTWSJWDKjY/O595zCrNy/BT2/uPRya9UrHoRcwzNV0Xxk9cVSqSkaNBC7CU/1
QnDw8A/up/x4iNJf6z5PKCqUzJAWbgVQws9ATHzLr+CeCPOFAxZKE0Ai0dV2jNdi
oiZXAZarFCL/xQA1cJYXO5dQMsBKr7so4VZ8omSOYU6Ky6XEifBoIs6395g5+yxq
TlYDZYstPx1Rf1mYMuoQ5wIRCsA7jdK5A0aASqwFnJdGEwxR2Tu/b4DqISwRr48S
9oVahzPKuQINBF5q0TYBEACvCOW16MFimC6FbAHyLfHrF7rzNk0bPUoxeTnP0J8X
AxzVho0zYt9pwvfVaZxSFOEoOmGFDdunhEE4apLfQRfN2q50XFGDBWToJdY/loCs
i2FGWjs+nO0IaBBm1G2uMJ+zdnO/96aHZiwu5xlkAY+v91xR3gkhoRd/GDFgJQBd
ZZXFJJM9zMNI+wKN/K9oBF38IE3HzM7OsQuzUcfmz4fxlLOAT4SCdGXjEWtJ0j/p
B6fjJz/n8g9YhilB77wgxAEJLMZ99wkugK2EWm+Ofzy9xg+/sLskJ5dIUZhFDpwM
fVK46gA+14c/WK5NTJujYp5p6lxhqK7Ja8zTRCHF1cOpFiJm3nRDZeM9cufpZeIA
mWgr8FMDQIA/oco8Axx6V7af7j3tXHmkEZMSxE2/SrKNYE13l+Lrm13TLB0hvJRd
ous5RI7Ml4vPcJN+/4gLpdznR7EjhMPZ362CtGwiJ5tDDFD9SK3kNKfNXJF2gYsC
KCzppGMsL40dMKEzK35w50tCvr8DBhnBIY/DuZybl5ktl0cnmzPTk0v06F5fMlE4
E/bi/UDDctwKzEdYg1SXMfY3OHZcduVELYRn+7O7i6EBiASuQU7wIz73+rzKSQLy
tTkH4/96ah7TfO4uIZHpXgbikY2r8AhTFR/njqRkllaJCU/gyAKVJmUGH+ah0+ZZ
sQARAQABiQIfBBgBCgAJBQJeatE2AhsMAAoJEBkOqQpczdT1Ne0P/RPiMBCVUrW6
IA/PuiHygaDrhVFgWtRmVm6vQkhE7fxNXUiDf/Ud+iX+3Y3XQM2vFqXjHVpI66i1
OhJ8mV9TwuRh60l/gUBL24xXWJS+JYOZ1C963v05ZR9VTg33p8y9F8k1DxlGzpHr
oepoOvsF4CkdpnH0v1fpKV3tSWhTh2JP/5P0VGZZLdWVHsJsMbcQBMTPrfbPnacM
J7DzRRfcjxjEB0cISimiYwDPDKUqB9AMykp7DPb/w1/vBtcT22s909Mg4ZQDiCBx
NtRPGMXmaOlSjpJH3dfjlH+YDa/UNOn7pItyhz8eyeoVPMLEAfQoX72pXLSPEuro
tMyHcpos14WbZAyxyr04K3oeHjhr/zOqsimu08Umb8TGhYPv27FMqVxTGiAwuWAI
0DXVraLMrEzxx6XXywQa4wA8enP95ZZD8xHB7YGvCgwb/FyR8TMtp/j0neGD+wAC
9SgWLbYqqJIFFSWWNGxWHZ1iwflbTTWWsE6W5odOAxOAPArXLXKagkvtVrNz9127
SwagEnrl0kGfmbpnOEnJYk4AvCHy1e1rL5To0lU4uPBacs5vQNLc4lrOi23NXQ/q
cIbBbZ+ze1y1x9c0uRpRVV47Zm2fvaMMMh4OGf09x0C3WaWE5CR9TfOpmOqybI9i
mae7WLtydkQnM7Shc1l2CmBCHH8ClSJN
=DsnN
-----END PGP PUBLIC KEY BLOCK-----
"""
ha_public_key_fingerprint = 'DB4C5FCCD0A466F87A05C2E1190EA90A5CCDD4F5'

logger = logging.getLogger(__name__)

class ConfigCipher:
    def __init__(self, loglevel):
        logging.basicConfig(level=loglevel.upper())
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
        self.gpg = gnupg.GPG()
        if not 'GPG_TTY' in os.environ or os.environ['GPG_TTY'] == '':
            os.environ['GPG_TTY'] = os.ttyname(0)
        logger.debug('ConfigCipher: GPG_TTY={}'.format(os.environ['GPG_TTY']))

    def list_keys(self):
        gpg = self.gpg
        logger.info('key list={}'.format(json.dumps(gpg.list_keys(), indent=4)))

    def delete_key(self, keyid, email='', passphrase=None):
        gpg = self.gpg
        logging.debug('keyid={} email={}'.format(keyid, email))
        found = False
        if not re.match(r'<.+@.+>', keyid) and email != '' and email != None:
            keyid = keyid + ' <' + email + '>'
        for key in gpg.list_keys(True):
            if 'uids' in key and keyid in key['uids']:
                logger.debug('delete_key: private key found={}'.format(json.dumps(key, indent=4)))
                logger.debug('delete_key: passphrase={}'.format(passphrase))
                if passphrase is None:
                    gpg.delete_keys(key['fingerprint'], True, expect_passphrase=False)
                else:
                    gpg.delete_keys(key['fingerprint'], True, passphrase=passphrase)
                found = True
        for key in gpg.list_keys():
            if 'uids' in key and keyid in key['uids']:
                logger.debug('delete_key: public key found={}'.format(json.dumps(key, indent=4)))
                gpg.delete_keys(key['fingerprint'])
                found = True
        if not found:
            logger.warning('delete_key: not found keyid={}'.format(keyid))

    def vendor_key(self, keyid, email):
        gpg = self.gpg
        logging.debug('vendor_key: keyid={} email={}'.format(keyid, email))
        keyid_email = keyid
        if not re.match(r'<.+@.+>', keyid) and email:
            keyid_email = keyid + ' <' + email + '>'
        found = 0
        for key in gpg.list_keys():
            if 'uids' in key and keyid_email in key['uids']:
                logger.debug('vendor_key: found={}'.format(json.dumps(key, indent=4)))
                vendor_key_fingerprint = key['fingerprint']
                found = found + 1
        if found > 1:
            logger.warning('vendor_key: {} keys found, using {}'.format(found, vendor_key_fingerprint))
        elif found == 0:
            logger.debug('vendor_key: generating a key keyid={}'.format(keyid))
            input_data = gpg.gen_key_input(key_type='RSA', key_length=4096, subkey_type='RSA', subkey_length=4096, expire_date=0, name_real=keyid, name_email=email)
            vendor_key = gpg.gen_key(input_data)
            vendor_key_fingerprint = str(vendor_key)
            logger.debug('vendor_key: generated key={}'.format(vendor_key_fingerprint))

        return vendor_key_fingerprint

    def import_ha_public_key(self):
        gpg = self.gpg
        for key in gpg.list_keys():
            if 'fingerprint' in key and key['fingerprint'] == ha_public_key_fingerprint:
                gpg.trust_keys(ha_public_key_fingerprint, 'TRUST_ULTIMATE')
                return ha_public_key_fingerprint
        import_result = gpg.import_keys(ha_public_key)
        if import_result.count != 1:
            logger.error('encrypt_config_json: failed importing a public key')
            return None
        fingerprint = import_result.fingerprints[0]
        logger.debug('encrypt_config_json: public key fingerprint={}'.format(fingerprint))
        gpg.trust_keys(fingerprint, 'TRUST_ULTIMATE')
        return fingerprint

    def encrypt_config_json(self, config_json, email=None, keyid='secure_build'):
        gpg = self.gpg

        vendor_key_fingerprint = self.vendor_key(keyid, email)
        if vendor_key_fingerprint == '':
            logging.error('encrypt_config_json: failed obtaining a vendor key keyid={}'.format(keyid))
            return None
        logging.debug('encrypt_config_json: vendor_key_fingerprint={}'.format(vendor_key_fingerprint))
        config_json['vendor_key'] = gpg.export_keys(vendor_key_fingerprint)

        logger.debug('encrypt_config_json: config_json={}'.format(json.dumps(config_json, indent=4)))

        fingerprint = self.import_ha_public_key()
        if fingerprint is None:
            logging.error('encrypt_config_json: failed importing ha public key')
            return None

        logger.debug('encrypt_config_json: key list={}'.format(json.dumps(gpg.list_keys(), indent=4)))

        encrypted_ascii_data = gpg.encrypt(json.dumps(config_json), fingerprint, sign=vendor_key_fingerprint, armor=True)
        if not encrypted_ascii_data.ok:
            logger.error('encrypt_config_json: failed encrypting config json status={}'.format(encrypted_ascii_data.status))
            return None
        logger.debug('ok={} status={}'.format(encrypted_ascii_data.ok, encrypted_ascii_data.status))
        return str(encrypted_ascii_data)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='registration_file.py')
    parser.add_argument('command', help='[encrypt|list-keys|delete-key]')
    parser.add_argument('--loglevel', default='INFO', help='loglevel')
    parser.add_argument('--config-json-path', help='clear text config json file')
    parser.add_argument('--rd-path', help='encrypted registration file')
    parser.add_argument('--key-id', default='secure-build', help='vendor key id')
    parser.add_argument('--email', help='vendor key user email')
    #parser.add_argument('--passphrase', help='Vendor key id passphrase')
    args = parser.parse_args()

    for name in vars(args).keys():
        if vars(args)[name]:
            logger.debug(name + ' ' + str(vars(args)[name]))

    config_cipher = ConfigCipher(args.loglevel)

    if args.command == 'encrypt':
        try:
            with open(os.path.expanduser(args.config_json_path)) as f:
                config_json = json.load(f)
        except Exception as e:
            logger.error('failed reading config json file e={}'.format(e))
            sys.exit(-1)
        encrypted_config_json = config_cipher.encrypt_config_json(config_json, email=args.email, keyid=args.key_id)
        try:
            with open(os.path.expanduser(args.rd_path), 'w') as f:
                f.write(encrypted_config_json)
        except Exception as e:
            logger.error('failed writing registration file e={}'.format(e))
            sys.exit(-1)
    elif args.command == 'list-keys':
        config_cipher.list_keys()
    elif args.command == 'delete-key':
        config_cipher.delete_key(args.key_id, email=args.email)
    else:
        logger.error('unknown command: {}'.format(args.command))