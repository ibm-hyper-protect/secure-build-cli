#! /usr/bin/python3
#
# Licensed Materials - Property of IBM
#
# 5737-I09
#
# Copyright IBM Corp. 2019 All Rights Reserved.
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp
#
import random
from OpenSSL import crypto

def setX509Attr(x509, attribute):
    try:
        (label, value) = attribute.split('=')
        x509.__setattr__(label, value)
    except Exception as e:
        print('failed to set {} as {}: error={}'.format(label, value, e))    

# subject string can be one of the following patterns
# '/C=US/ST=NY/L=Armonk/O=IBM/OU=Hyper Protect/CN=Common Name'
# 'CN=Common Name'
# 'Common Name'
def setX509Name(x509, subject):
    if not '/' in subject:
        if '=' in subject:
            setX509Attr(x509, subject)
        else:
            x509.commonName = subject
        return
    attributes = subject.split('/')
    for attribute in attributes:
        if '=' in attribute:
            setX509Attr(x509, attribute)

# Used to extract san value from a certificate
def getSANValue(cert_path):
     server_cert = crypto.load_certificate(crypto.FILETYPE_PEM, open(cert_path).read())
     san = ''
     ext_count = server_cert.get_extension_count()
     for i in range(0, ext_count):
        ext = server_cert.get_extension(i)
        if 'subjectAltName' in str(ext.get_short_name()):
            san = ext.__str__()
     return san


def gen_ca(ca_subject, ca_path, ca_key_path):
    ca_key = crypto.PKey()
    ca_key.generate_key(crypto.TYPE_RSA, 2048)
    ca_key_bytes = crypto.dump_privatekey(crypto.FILETYPE_PEM, ca_key)

    with open(ca_key_path, 'w') as f:
        f.write(ca_key_bytes.decode('utf-8'))

    ca_cert = crypto.X509()
    ca_cert.set_version(2)
    ca_cert.set_serial_number(random.randint(50000000,100000000))

    ca_subj = ca_cert.get_subject()
    setX509Name(ca_subj, ca_subject)

    ca_cert.add_extensions([
        crypto.X509Extension(b'subjectKeyIdentifier', False, b'hash', subject=ca_cert),
    ])

    ca_cert.add_extensions([
        crypto.X509Extension(b'authorityKeyIdentifier', False, b'keyid:always', issuer=ca_cert),
    ])

    ca_cert.add_extensions([
        crypto.X509Extension(b'basicConstraints', True, b'CA:TRUE'),
        crypto.X509Extension(b'extendedKeyUsage', False, b'clientAuth,serverAuth'),
        crypto.X509Extension(b'keyUsage', False, b'keyCertSign, cRLSign'),
    ])

    ca_cert.set_issuer(ca_subj)
    ca_cert.set_pubkey(ca_key)

    ca_cert.gmtime_adj_notBefore(0)
    ca_cert.gmtime_adj_notAfter(60*60*24*365*2) # 2 years

    ca_cert.sign(ca_key, 'sha256')

    ca_cert_bytes = crypto.dump_certificate(crypto.FILETYPE_PEM, ca_cert)

    with open(ca_path, 'w') as f:
        f.write(ca_cert_bytes.decode('utf-8'))

    return ca_cert, ca_key

def gen_csr(cert_subject, csr_path, cert_key_path):
    cert_key = crypto.PKey()
    cert_key.generate_key(crypto.TYPE_RSA, 2048)
    cert_key_bytes = crypto.dump_privatekey(crypto.FILETYPE_PEM, cert_key)

    with open(cert_key_path, 'w') as f:
        f.write(cert_key_bytes.decode('utf-8'))

    csr = crypto.X509Req()
    csr_subj = csr.get_subject()
    setX509Name(csr_subj, cert_subject)
    csr.set_pubkey(cert_key)
    csr.sign(cert_key, 'sha256')
    csr_bytes = crypto.dump_certificate_request(crypto.FILETYPE_PEM, csr)

    with open(csr_path, 'w') as f:
        f.write(csr_bytes.decode('utf-8'))

    return csr, cert_key

def sign_csr(cert_path, csr_path, ca_path, ca_key_path):
    csr = crypto.load_certificate_request(crypto.FILETYPE_PEM, open(csr_path).read())
    ca_cert = crypto.load_certificate(crypto.FILETYPE_PEM, open(ca_path).read())
    ca_key = crypto.load_privatekey(crypto.FILETYPE_PEM, open(ca_key_path).read())

    cert = crypto.X509()
    cert.set_version(2)
    cert.set_serial_number(random.randint(50000000,100000000))
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(60*60*24*365) # 1 year
    cert.add_extensions([
    crypto.X509Extension(b'basicConstraints', False, b'CA:FALSE'),
        crypto.X509Extension(b'subjectKeyIdentifier', False, b'hash', subject=cert),
    ])
    cert.add_extensions([
        crypto.X509Extension(b'authorityKeyIdentifier', False, b'keyid:always', issuer=ca_cert),
        crypto.X509Extension(b'extendedKeyUsage', False, b'clientAuth,serverAuth'),
        crypto.X509Extension(b'keyUsage', False, b'digitalSignature'),
    ])
    cert.add_extensions(csr.get_extensions())
    cert.set_issuer(ca_cert.get_subject()) # ca subject
    cert.set_subject(csr.get_subject())
    cert.set_pubkey(csr.get_pubkey())
    cert.sign(ca_key, 'sha256') # ca key

    cert_bytes = crypto.dump_certificate(crypto.FILETYPE_PEM, cert)

    with open(cert_path, 'w') as f:
        f.write(cert_bytes.decode('utf-8'))

    return cert 

def sign_server_csr(cert_path, csr_path, ca_path, ca_key_path, san=[]):
    csr = crypto.load_certificate_request(crypto.FILETYPE_PEM, open(csr_path).read())
    ca_cert = crypto.load_certificate(crypto.FILETYPE_PEM, open(ca_path).read())
    ca_key = crypto.load_privatekey(crypto.FILETYPE_PEM, open(ca_key_path).read())

    cert = crypto.X509()
    cert.set_version(2)
    cert.set_serial_number(random.randint(50000000,100000000))
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(60*60*24*365) # 1 year
    cert.add_extensions([
    crypto.X509Extension(b'basicConstraints', False, b'CA:FALSE'),
        crypto.X509Extension(b'subjectKeyIdentifier', False, b'hash', subject=cert),
    ])
    cert.add_extensions([
        crypto.X509Extension(b'authorityKeyIdentifier', False, b'keyid:always', issuer=ca_cert),
        crypto.X509Extension(b'extendedKeyUsage', False, b'serverAuth'),
        crypto.X509Extension(b'keyUsage', False, b'digitalSignature'),
        crypto.X509Extension(b'subjectAltName', False, ','.join(san).encode()),
    ])
    cert.add_extensions(csr.get_extensions())
    cert.set_issuer(ca_cert.get_subject()) # ca subject
    cert.set_subject(csr.get_subject())
    cert.set_pubkey(csr.get_pubkey())
    cert.sign(ca_key, 'sha256') # ca key

    cert_bytes = crypto.dump_certificate(crypto.FILETYPE_PEM, cert)

    with open(cert_path, 'w') as f:
        f.write(cert_bytes.decode('utf-8'))

    return cert