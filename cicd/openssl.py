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
import ipaddress
import datetime
from OpenSSL import crypto
from cryptography import x509 as cx509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.backends import default_backend

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

# Build a cryptography Name from a subject string
_SUBJECT_ATTR_MAP = {
    'C':  NameOID.COUNTRY_NAME,
    'ST': NameOID.STATE_OR_PROVINCE_NAME,
    'L':  NameOID.LOCALITY_NAME,
    'O':  NameOID.ORGANIZATION_NAME,
    'OU': NameOID.ORGANIZATIONAL_UNIT_NAME,
    'CN': NameOID.COMMON_NAME,
}

def _build_name(subject):
    attrs = []
    if '/' in subject:
        parts = subject.split('/')
        for part in parts:
            if '=' in part:
                label, value = part.split('=', 1)
                oid = _SUBJECT_ATTR_MAP.get(label.strip())
                if oid:
                    attrs.append(cx509.NameAttribute(oid, value))
    elif '=' in subject:
        label, value = subject.split('=', 1)
        oid = _SUBJECT_ATTR_MAP.get(label.strip())
        if oid:
            attrs.append(cx509.NameAttribute(oid, value))
    else:
        attrs.append(cx509.NameAttribute(NameOID.COMMON_NAME, subject))
    return cx509.Name(attrs)

# Parse a SAN entry string like 'DNS:hostname' or 'IP:1.2.3.4' into a GeneralName
def _parse_san_entry(entry):
    entry = entry.strip()
    if entry.startswith('DNS:'):
        return cx509.DNSName(entry[4:])
    elif entry.startswith('IP:'):
        return cx509.IPAddress(ipaddress.ip_address(entry[3:]))
    elif entry.startswith('email:'):
        return cx509.RFC822Name(entry[6:])
    elif entry.startswith('URI:'):
        return cx509.UniformResourceIdentifier(entry[4:])
    else:
        return cx509.DNSName(entry)

# Used to extract san value from a certificate
def getSANValue(cert_path):
    cert_crypto = cx509.load_pem_x509_certificate(open(cert_path, 'rb').read(), backend=default_backend())
    try:
        san_ext = cert_crypto.extensions.get_extension_for_class(cx509.SubjectAlternativeName)
        # Reproduce the OpenSSL text representation, e.g. "DNS:hostname, IP Address:1.2.3.4"
        parts = []
        for name in san_ext.value:
            if isinstance(name, cx509.DNSName):
                parts.append('DNS:' + name.value)
            elif isinstance(name, cx509.IPAddress):
                parts.append('IP Address:' + str(name.value))
            elif isinstance(name, cx509.RFC822Name):
                parts.append('email:' + name.value)
            elif isinstance(name, cx509.UniformResourceIdentifier):
                parts.append('URI:' + name.value)
            else:
                parts.append(str(name))
        return ', '.join(parts)
    except cx509.ExtensionNotFound:
        return ''


def gen_ca(ca_subject, ca_path, ca_key_path):
    # Generate RSA private key
    ca_key_crypto = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )

    ca_key_bytes = ca_key_crypto.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )

    with open(ca_key_path, 'w') as f:
        f.write(ca_key_bytes.decode('utf-8'))

    name = _build_name(ca_subject)
    serial = random.randint(50000000, 100000000)
    now = datetime.datetime.now(datetime.timezone.utc)

    ca_cert_crypto = (
        cx509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(ca_key_crypto.public_key())
        .serial_number(serial)
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=365 * 2))
        .add_extension(cx509.SubjectKeyIdentifier.from_public_key(ca_key_crypto.public_key()), critical=False)
        .add_extension(cx509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key_crypto.public_key()), critical=False)
        .add_extension(cx509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(cx509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH, ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(cx509.KeyUsage(
            digital_signature=False, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=True,
            crl_sign=True, encipher_only=False, decipher_only=False,
        ), critical=False)
        .sign(ca_key_crypto, hashes.SHA256(), backend=default_backend())
    )

    ca_cert_bytes = ca_cert_crypto.public_bytes(serialization.Encoding.PEM)

    with open(ca_path, 'w') as f:
        f.write(ca_cert_bytes.decode('utf-8'))

    # Return pyOpenSSL objects so callers using crypto.dump_certificate / crypto.dump_privatekey continue to work
    ca_cert = crypto.X509.from_cryptography(ca_cert_crypto)
    ca_key = crypto.PKey.from_cryptography_key(ca_key_crypto)
    return ca_cert, ca_key

def gen_csr(cert_subject, csr_path, cert_key_path):
    cert_key_crypto = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )

    cert_key_bytes = cert_key_crypto.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )

    with open(cert_key_path, 'w') as f:
        f.write(cert_key_bytes.decode('utf-8'))

    name = _build_name(cert_subject)
    csr_crypto = (
        cx509.CertificateSigningRequestBuilder()
        .subject_name(name)
        .sign(cert_key_crypto, hashes.SHA256(), backend=default_backend())
    )

    csr_bytes = csr_crypto.public_bytes(serialization.Encoding.PEM)

    with open(csr_path, 'w') as f:
        f.write(csr_bytes.decode('utf-8'))

    # Return pyOpenSSL PKey so callers using crypto.dump_privatekey continue to work
    cert_key = crypto.PKey.from_cryptography_key(cert_key_crypto)
    return csr_crypto, cert_key

def sign_csr(cert_path, csr_path, ca_path, ca_key_path):
    csr_crypto = cx509.load_pem_x509_csr(open(csr_path, 'rb').read(), backend=default_backend())
    ca_cert_crypto = cx509.load_pem_x509_certificate(open(ca_path, 'rb').read(), backend=default_backend())
    ca_key_crypto = serialization.load_pem_private_key(open(ca_key_path, 'rb').read(), password=None, backend=default_backend())

    serial = random.randint(50000000, 100000000)
    now = datetime.datetime.now(datetime.timezone.utc)

    builder = (
        cx509.CertificateBuilder()
        .subject_name(csr_crypto.subject)
        .issuer_name(ca_cert_crypto.subject)
        .public_key(csr_crypto.public_key())
        .serial_number(serial)
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(cx509.BasicConstraints(ca=False, path_length=None), critical=False)
        .add_extension(cx509.SubjectKeyIdentifier.from_public_key(csr_crypto.public_key()), critical=False)
        .add_extension(cx509.AuthorityKeyIdentifier.from_issuer_public_key(ca_cert_crypto.public_key()), critical=False)
        .add_extension(cx509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH, ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(cx509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=False,
            crl_sign=False, encipher_only=False, decipher_only=False,
        ), critical=False)
    )

    # Copy SAN extension from CSR if present
    try:
        san_ext = csr_crypto.extensions.get_extension_for_class(cx509.SubjectAlternativeName)
        builder = builder.add_extension(san_ext.value, critical=san_ext.critical)
    except cx509.ExtensionNotFound:
        pass

    cert_crypto = builder.sign(ca_key_crypto, hashes.SHA256(), backend=default_backend())
    cert_bytes = cert_crypto.public_bytes(serialization.Encoding.PEM)

    with open(cert_path, 'w') as f:
        f.write(cert_bytes.decode('utf-8'))

    return crypto.X509.from_cryptography(cert_crypto)

def sign_server_csr(cert_path, csr_path, ca_path, ca_key_path, san=[]):
    csr_crypto = cx509.load_pem_x509_csr(open(csr_path, 'rb').read(), backend=default_backend())
    ca_cert_crypto = cx509.load_pem_x509_certificate(open(ca_path, 'rb').read(), backend=default_backend())
    ca_key_crypto = serialization.load_pem_private_key(open(ca_key_path, 'rb').read(), password=None, backend=default_backend())

    serial = random.randint(50000000, 100000000)
    now = datetime.datetime.now(datetime.timezone.utc)

    san_names = [_parse_san_entry(entry) for entry in san if entry.strip()]

    builder = (
        cx509.CertificateBuilder()
        .subject_name(csr_crypto.subject)
        .issuer_name(ca_cert_crypto.subject)
        .public_key(csr_crypto.public_key())
        .serial_number(serial)
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(cx509.BasicConstraints(ca=False, path_length=None), critical=False)
        .add_extension(cx509.SubjectKeyIdentifier.from_public_key(csr_crypto.public_key()), critical=False)
        .add_extension(cx509.AuthorityKeyIdentifier.from_issuer_public_key(ca_cert_crypto.public_key()), critical=False)
        .add_extension(cx509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(cx509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=False,
            crl_sign=False, encipher_only=False, decipher_only=False,
        ), critical=False)
        .add_extension(cx509.SubjectAlternativeName(san_names), critical=False)
    )

    # Copy additional extensions from CSR (excluding SAN already set above)
    for ext in csr_crypto.extensions:
        if ext.oid != cx509.SubjectAlternativeName.oid:
            builder = builder.add_extension(ext.value, critical=ext.critical)

    cert_crypto = builder.sign(ca_key_crypto, hashes.SHA256(), backend=default_backend())
    cert_bytes = cert_crypto.public_bytes(serialization.Encoding.PEM)

    with open(cert_path, 'w') as f:
        f.write(cert_bytes.decode('utf-8'))

    return crypto.X509.from_cryptography(cert_crypto)
