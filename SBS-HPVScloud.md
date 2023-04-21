The following diagram illustrates a high level structure of SBS, which is provisioned by an administrator by using the [IBM Cloud CLI](https://cloud.ibm.com/docs/cli?topic=cli-hpvs_cli_plugin). This document describes how a developer can interact with the server by using the `build.py` script. A developer prepares the source code of an application with Dockerfile, in a source code repository such as GitHub. The build server pulls the source code, builds a container image by using the Dockerfile, signs it, and pushes it to a container registry, such as Docker Hub. During the build process, it also creates a manifest file and signs it.

Optionally, it can push the manifest to Cloud Object Storage, or the developer can download it on a local file system. The build server can also export and import its state as a single file, which includes signing keys of the image and manifest, with build parameters. When exported, the state is encrypted in such a way that the developer or IBM cannot decrypt the state image outside the enclave. It can be decrypted only inside the enclave. The encrypted state image can be pushed to Cloud Object Storage, or the developer can download it on a local file system.

<p align="center">
  <img src="./images/secure-build.png">
</p>

## Before you begin

The following is a list of hardware or software requirements:
- Linux management server from where you can run the build CLI tool (Linux workstation or VM).
  - x86 architecture (recommended 2 CPUs/4GB memory or more)
  - Ubuntu 20.04 or 18.04 (64 bit)
  - Python 3.8 (Python 2.x is not supported)
- Access to GitHub for hosting the source code.
- Dockerfile (everything that you need to build your container image).
- Access to IBM Cloud Registry or DockerHub.
- (Optional) Access to IBM Cloud Object Storage (COS) Service.
- Access to IBM Hyper Protect Virtual Servers.
- Registration definition file of Secure Build Server (secure_build.asc) from [step 2](https://cloud.ibm.com/docs/hp-virtual-servers?topic=hp-virtual-servers-imagebuild#deploysecurebuild).


## Install the Secure Build CLI
The CLI script is written in Python and has been tested using Python 3.6.9. You must install Python3 and pip3, if you don't have them on your client system. The `build.py` is the main script that comes with secure-build-cli. This script helps you to interact and do the required operations on the SBS instance after it is created by using the IBM Cloud CLI. For systems that run Ubuntu, you can run the following commands to install them.
```
apt-get update
apt-get install python3 python3-pip
python3 -m pip install -U pip
```

After you run the commands listed above, clone the repository, and install the dependencies by running the following commands:

```
git clone git@github.com:ibm-hyper-protect/secure-build-cli.git
cd secure-build-cli
pip3 install -r requirements.txt
```


## Preparing the configuration
Create the `sbs-config.json` file in any location you choose on your local machine, and add the following content in the file:
```
{
  "HOSTNAME": "sbs.example.com",
  "RUNTIME_TYPE": "classic",
  "CICD_PORT": "443",
  "IMAGE_TAG": "",
  "GITHUB_KEY_FILE": "~/.ssh/id_rsa",
  "GITHUB_URL": "git@github.com:<git_user>/<git_repo>.git",
  "GITHUB_BRANCH": "main",
  "GITHUB_RECURSE_SUBMODULES": "True",
  "CONTAINER_NAME": "SBContainer",
  "REPO_ID": "sbs",
  "DOCKER_REPO": "<docker_namespace>/<docker_repository_name>",
  "DOCKER_USER": "<docker_user>",
  "DOCKER_PASSWORD": "<docker_password>",
  "IMAGE_TAG_PREFIX": "<docker_image_tag>",
  "DOCKER_CONTENT_TRUST_BASE": "False",
  "DOCKER_CONTENT_TRUST_BASE_SERVER": "",
  "DOCKER_RO_USER": "<docker_user>",
  "DOCKER_RO_PASSWORD": "<docker_password>",
  "DOCKER_BASE_USER": "",
  "DOCKER_BASE_PASSWORD": "",
  "ICR_BASE_REPO": "",
  "ICR_BASE_REPO_PUBLIC_KEY": "",
  "ENV_WHITELIST":  ["<KEY1>", "<KEY2>"],
  "ARG": {
    "<BUILD_ARG1>": "<VALUE1>",
    "<BUILD_ARG2>": "<VALUE2>"
  },
  "ISV_SECRET": {
       "k1": "secret1",
       "k2": "secret2"
  }
}
```

Where
```
HOSTNAME - Hostname of the SBS server which will be used while generating certificates and communicating with the secure build server.
RUNTIME_TYPE - set to classic to leverage [IBM Cloud Hyper Protect Virtual Servers](https://cloud.ibm.com/catalog/services/hyper-protect-virtual-server)
CICD_PORT - port on which a build service is running (default: 443).
IMAGE_TAG - image tag of the container image to be deployed as SBS server. Use "1.3.0.10" unless otherwise noted.
GITHUB_KEY_FILE - Private key path to access your GitHub repo.
GITHUB_URL - GitHub URL.
GITHUB_BRANCH - GitHub branch name.
GITHUB_RECURSE_SUBMODULES - If you want to clone submodules, then add this parameter and make the value true.
CONTAINER_NAME - Name of the Hyper Protect Virtual Servers instance which you want to create on cloud. This name can be different from the name which you use on cloud. The name is used as a part of a certificate file name. You can choose any valid string as a file name.
REPO_ID - This is the ID which is used as a prefix of the registration definition file for a newly built image.
DOCKER_REPO - DockerHub repository.
DOCKER_USER - docker user name who has write access to above repository.
DOCKER_PASSWORD - docker password who has write access to above repository.
IMAGE_TAG_PREFIX - a prefix of the image tag for the image to be built. The full image tag will be IMAGE_TAG_PREFIX + '-' + the leading seven digits from the GitHub repository hash.
DOCKER_CONTENT_TRUST_BASE - If your base image that is mentioned in the Dockerfile is signed, then make it true.
DOCKER_CONTENT_TRUST_BASE_SERVER - If your base image mentioned in the Dockerfile is signed, then you can specify the notary URL (default: https://notary.docker.io).
DOCKER_BASE_USER - docker user name of repository which has base image.
DOCKER_BASE_PASSWORD - docker password of repository which has base image.
DOCKER_RO_USER - you can use the same as DOCKER_USER. It is recommended that you specify a user who has read access only to your Docker repository.
DOCKER_RO_PASSWORD - you can use same as DOCKER_PASSWORD. It is recommended that you specify a user who has read access only to your Docker repository.
ENV_WHITELIST - All environment variable names need to be listed. The Hyper Protect Virtual Servers don't allow any environment variable unless it is in this list because of a security reason.
ARG - You have to pass all build argument parameters as you pass during Docker build.
ICR_BASE_REPO - Base Image used in dockerfile if it is present in ICR
ICR_BASE_REPO_PUBLIC_KEY - public key with which the base image used in docker file (ICR_BASE_REPO) is signed
ISV_SECRET - Use to provide the ISV secrets as a key and value pair. The secrets are added in the ``/isv_secrets/secrets.json` file within the IBM Hyper Protect Virtual server.
```
Note:
- If you use IBM Cloud Registry instead of DockerHub registry, then you must use the following parameters:
  ```buildoutcfg
  "DOCKER_BASE_SERVER": "<domain_name>",
  "DOCKER_PUSH_SERVER": "<domain_name>",
  "DOCKER_USER": "iamapikey",
  "DOCKER_PASSWORD": "<ibm_cloud_apikey>"
  "DOCKER_RO_USER": "iamapikey",
  "DOCKER_RO_PASSWORD": "<ibm_cloud_apikey>",
  "DOCKER_CONTENT_TRUST_PUSH_SERVER": "https://<domain_name>"
  ```

  - The `<domain_name>` specifies the location of IBM Cloud Container Registry (e.g. `us.icr.io`). Select the domain name for one of [available regions](https://cloud.ibm.com/docs/Registry?topic=Registry-registry_overview#registry_regions).
  - If you are using the IBM Cloud Registry server, and you specified the `<domain_name>` as `us.icr.io`, then specify `us.icr.io` as the value for `DOCKER_CONTENT_TRUST_PUSH_SERVER`. As another example, if value of `DOCKER_REPO=de.icr.io`, then the value of `DOCKER_CONTENT_TRUST_PUSH_SERVER` should be `de.icr.io`. To know more about IBM Cloud registry, see [Getting started with IBM Cloud Container Registry](https://cloud.ibm.com/docs/Registry?topic=Registry-getting-started).

- If the base image used in Docker file is signed, configure "DOCKER_CONTENT_TRUST_BASE" with a value "True". And configure "DOCKER_BASE_USER" and "DOCKER_BASE_PASSWORD" with the credentials.
  - If the base image is on Docker Hub and DCT signed, "DOCKER_CONTENT_TRUST_BASE_SERVER" is set with the notary server URL https://notary.docker.io.
  - If the base image is on IBM Cloud Container Registry and Red Hat Simple Signed, "DOCKER_CONTENT_TRUST_BASE_SERVER" is set with <domain_name>.
  - If the base image is on IBM Cloud Container Registry and Red Hat Simple Signed, you must provide the 'ICR_BASE_REPO', and 'ICR_BASE_REPO_PUBLIC_KEY' parameters. The following is an example for these two values:
    - "ICR_BASE_REPO": `"<region>.icr.io/<repo name>/<image name>:<tag>"`
    - "ICR_BASE_REPO_PUBLIC_KEY" : `"<path to the public key>"`

- If the base image used in Docker file is unsigned, set "DOCKER_CONTENT_TRUST_BASE" to "false". Also, you don't have to set "DOCKER_CONTENT_TRUST_BASE_SERVER".
   - If the base image is on IBM Cloud Container Registry, the "DOCKER_BASE_USER" and "DOCKER_BASE_PASSWORD" must be set.
   - If the base image is on Docker Hub and is private, you must set the "DOCKER_BASE_USER" and "DOCKER_BASE_PASSWORD". Otherwise, you don't have to set the "DOCKER_BASE_USER" and "DOCKER_BASE_PASSWORD" parameters.

- To update the hostname, or to update the instance with a new certificate when the old certificate expires, complete the following steps:
  1. Backup the `sbs-config.json` file, and edit the file to remove the "UUID" parameter.
  2. Update the hostname in the `sbs-config.json` (in the case of certificate expiration, you need not update the hostname).
  3. Regenerate the certificate by running the commands
    ```buildoutcfg
    ./build.py create-client-cert --env sbs-config.json
    ```
    and
    ```buildoutcfg
    ./build.py create-server-cert --env sbs-config.json
    ```
  4. Update the `/etc/hosts` file with the new hostname (in the case of certificate expiration, you need not update the hostname).
  5. Run the following command to get the new certificate:
     ```buildoutcfg
     ./build.py instance-env --env sbs-config.json
     ```
  6. Run the following command to update the SBS instance (in the case of certificate expiration, you need not update the hostname):
     ```buildoutcfg
     ibmcloud hpvs instance-update SBContainer --rd-path secure_build.asc -i 1.3.0.10 --hostname sbs.example.com -e CLIENT_CRT=... -e CLIENT_CA=... -e SERVER_CRT=... -e SERVER_KEY=...
     ```

Also see [Additional Build Parameters](additional-build-parameters.md).

## Deploying the Secure Build Server

Complete the following steps:

1. Install the IBM Cloud CLI, and the HPVS plugin.
```buildoutcfg
curl -sL https://raw.githubusercontent.com/IBM-Cloud/ibm-cloud-developer-tools/master/linux-installer/idt-installer | bash
ibmcloud plugin install container-registry -r Bluemix -f
ibmcloud plugin install hpvs
```

Note: Update the IBM Cloud CLI if it is installed already.

2. Log in to IBM Cloud by using either an API key, or the Single Sign On (SSO) authentication. See [Getting started with the IBM Cloud CLI](https://cloud.ibm.com/docs/cli?topic=cli-getting-started) for more details.

3. Configure the `sbs-config.json` file with certificates by using one of the following options.
   1. Use build.py to create certificate-authority (CA) and client certificates which are used for secure communication from your client script to the SBS instance.
      ```buildoutcfg
      ./build.py create-client-cert --env <path>/sbs-config.json
      ```
      After you execute above command, a directory is generated that looks like this: `.SBContainer-9ab033ad-5da1-4c4e-8eae-ca8c468dbbcc.d`.
      You will notice that two parameters "UUID" and "SECRET", are added to the `sbs-config.json` file.
      UUID is used along with the container name where the generated certificates are stored.
      SECRET holds a randomly generated value, which needs to be preserved safely, and is used to deal with the state image of SBS. Continue to step #4.  
      Note:-      
      - Follow the best practices of certificate management.  
      - The CA certificate should not be compromised or revoked.  
      - Third-party certificates are not supported.  

   2. Use your own certificate-authority (CA) and client certificates.
      1. Go to the CLI directory. If it is located at `~/git`, run the following command:
         ```
         cd ~/git/secure-build-cli
         ```
      2. Add the following path names to the  `sbs-config.json` file.
         Note that the `server-csr.pem` and `server-cert.pem` do not exist as yet. If the `./sbs-keys` directory does not exist, you can create one by using the command `mkdir ./sbs-keys`.
         ```
         "CAPATH": "Path to CA certificate",
         "CAKEYPATH": "Path to CA key",
         "CLIENT_CRT_KEY": "Path to concatenated client cert and key",   //cat my-client-cert.pem my-client-cert-key.pem > my-client-cert-and-key.pem
         "CSRPATH": "./sbs-keys/server-csr.pem",
         "CERTPATH": "./sbs-keys/server-cert.pem",
         ```
         Note:-      
         - Follow the best practices of certificate management.
         - The CA certificate should not be compromised or revoked.
         - Third-party certificates are not supported.

4. Use build.py to create the server certificate signed by the CA certificate generated that was generated in the previous  step. It will be setup on the server for secure communication.
      ```buildoutcfg
      ./build.py create-server-cert --env <path>/sbs-config.json
      ```

5. Get the environment key value pair to be used in instance-create command by running the following command.
```buildoutcfg
./build.py instance-env --env <path>/sbs-config.json
```

6. Create the SBS instance on cloud. You can copy and paste the output from `instance-env` command as command-line parameters for the `instance-create` command.
```buildoutcfg
ibmcloud hpvs instance-create SBContainer lite-s dal13 --rd-path secure_build.asc -i 1.3.0.10 --hostname sbs.example.com -e CLIENT_CRT=... -e CLIENT_CA=... -e SERVER_CRT=... -e SERVER_KEY=...
```
Where:
- SBContainer is the name of the SBS instance to be created.
- lite-s is the plan name.
- dal13 is the region name.
- 1.3.0.10 is the image tag of Secure Docker Build docker image.
- hostname is the server hostname that was given in sbs-config.json.

To know more details about which plan to use and which region to use, see [hpvs instance-create](https://cloud.ibm.com/docs/hpvs-cli-plugin?topic=hpvs-cli-plugin-hpvs_cli_plugin#create_instance).

7. You can list the Hyper Protect Virtual Servers instances.
```buildoutcfg
ibmcloud hpvs instances
```
After the instance is up and running, you can see `Public IP address` in the instance list.

8. Map the Public IP address with the hostname provided for the server in /etc/hosts file.
```buildoutcfg
10.20.x.xx  abc.test.com
```

## How to build image by using SBS
After you create the SBS instance, complete the following steps to build your image securely:  

1. Check the status of SBS.
```buildoutcfg
./build.py status --env <path>/sbs-config.json
INFO:__main__:status: response={
    "status": ""
}
```
2. Initialize the configuration.
```buildoutcfg
./build.py init --env <path>/sbs-config.json
```
3. Build the image.
```buildoutcfg
./build.py build --env <path>/sbs-config.json
```
4. Check the build log.
```buildoutcfg
./build.py log --log build --env <path>/sbs-config.json
```
5. Check whether the image has been built and pushed successfully.
```buildoutcfg
./build.py status --env <path>/sbs-config.json
```
As the build progresses, the `status` response shows the last completed step.
Here is a typical sequence of responses for a successful build.
```
{
  ...
    "status": "cleaned up"
}
{
  ...
    "status": "github cloned"
}
{
  ...
    "status": "image built"
}
{
  ...
    "status": "image pushed"
}
{
  ...
    "status": "success"
}
```
When an error occurs, the `status` response shows the command that caused the error. Typically, you need to examine the build log to fix the issue.
```
{
  ...
    "status": "exiting due to a non-zero return value: 1, cmd: docker build --disable-content-trust=false -t docker.io/<user_name>/nginxapp:latest -f Dockerfile ."
}
```
To stop a long-running build process, see [How to stop and clean up a build process](SBS-HPVScloud.md#how-to-stop-and-clean-up-a-build-process).

## How to deploy the image that is built by using SBS
Complete the following steps:

1. Get an encrypted registration definition file.
```buildoutcfg
./build.py get-config-json --env <path>/sbs-config.json --key-id <key_id> --email <your_email_as_id>
```
e.g. `--key-id isv_user --email isv@example.com`

If you want to pass ISV SECRETS to the container, then pass the `--isv-secrets` flag and add the `ISV_SECRET` section in the `sbs-config.json` configuration file. The following is an example:
```buildoutcfg
./build.py get-config-json --env sbs-config.json --key-id secure-build-ad52e76-1 --isv-secrets
```

The `<key_id>` is for a GPG key to sign the file. If omitted, the default id is `secure-build`. The email address is used to identify the key. If omitted, the GPG library will pick up a default one, typically `<your_login_id>@<domain_name_of_client>`.

During the above command you will be asked to create a passphrase. Enter the passphrase twice (the second time is for confirmation). Then again passphrase will be asked to sign the file.

Now the registration definition file for the newly built image, `sbs.enc`, is stored in your current directory. The file name is `REPO_ID` in sbs-config.json + `.enc`.

2. Run the following command to get the python file that was generated to create a repository defintion file [ Optional ]
```
./build.py get-config-python --env <path>/sbs-config.json
```

3. Get the build image tag, which is `IMAGE_TAG_PREFIX` in sbs-config.json + `<suffix>`, by using one of the following options:

a. Run the following command to see the image tag after building the image.
```buildoutcfg
# ./build.py status --env <path>/sbs-config.json
INFO:__main__:status: response={
 ..........
    "image_tag": "s390x-v0.3-60fd72e",
..........
}
```
Use this `image_tag`.

b. You can log in to your container registry (e.g. Docker Hub) and check the tag.

4. Create the Hyper Protect Virtual Servers instance by using the `ibmcloud hpvs instance-create` command.
```buildoutcfg
ibmcloud hpvs instance-create container_name lite-s dal13 --rd-path sbs.enc -i image_tag --hostname sbs.example.com {-e listed_environment_variable1=value1 ...}
```

## Manifest file
The SBS instance creates a manifest file at each successful build as a snapshot of build materials for audit purposes. The developer can verify the integrity of the built image and the artifacts used for building the image. Using this Manifest file is optional.

## How to store Manifest file in IBM Cloud Object Storage

1. Add the following parameters to your `sbs-config.json` file.
```buildoutcfg
    "COS_API_KEY_ID": "<your_cloud_apikey>",
    "COS_RESOURCE_CRN": "<your_cloud_resource_crn_id>",
    "COS_ENDPOINT": "<your_public_cos_endpoint>",
    "COS_AUTH_ENDPOINT": "https://iam.cloud.ibm.com/oidc/token",
    "MANIFEST_BUCKET_NAME": "<your_bucket_name>",
```
`COS_ENDPOINT` specifies the public endpoint of your COS instance (e.g. https://s3.us-east.cloud-object-storage.appdomain.cloud). Don't forget the leading `https://`.
You need to create the bucket specified by `MANIFEST_BUCKET_NAME` if it doesn't exist.

2. Update the SBS instance with the new COS parameters.
```buildoutcfg
./build.py update --env <path>/sbs-config.json
```

3. Build the image.
```buildoutcfg
./build.py build --env <path>/sbs-config.json
```

This will store your manifest file to IBM Cloud Object Storage.


## How to get the Manifest file

1. Get the latest manifest file directly from SBS.
```buildoutcfg
./build.py get-manifest --env <path>/sbs-config.json
```

This will store your manifest file to current working directory, something similar to `manifest.docker.io.<user_name>.nginxapp.v1-d14cdc8.2021-02-04_13-25-52.512466.sig.tbz`.

2. Verifying the integrity of the Manifest file
```buildoutcfg
./build.py get-manifest --env <path>/sbs-config.json  --verify-manifest
```

## How to extract build materials from the Manifest file

Untar by using the `tar` command.
```buildoutcfg
tar -xvf manifest.docker.io.<user_name>.nginxapp.v1-d14cdc8.2021-02-04_13-25-52.512466.sig.tbz
manifest.docker.io.<user_name>.nginxapp.v1-d14cdc8.2021-02-04_13-25-52.512466.tbz
manifest.docker.io.<user_name>.nginxapp.v1-d14cdc8.2021-02-04_13-25-52.512466.sig
```

Further untar to get the build materials.
```buildoutcfg
tar -xvf manifest.docker.io.<user_name>.nginxapp.v1-d14cdc8.2021-02-04_13-25-52.512466.tbz
```

You will see a data and git folder.
- The data directory provides the `build.json` and `build.log` files which contain the build status and the build log, respectively.
- The git directory contains the snapshot of the cloned git repository of the source code on the SBS instance when the build was completed.

## How to extract Public Key Used for Signing Container Image inside SBS
```buildoutcfg
./build.py get-signed-image-publickey --env <path>/sbs-config.json
```
After you run this command, the <repo_name>'public.key' template file is created, which contains the public key that is used to sign the container image.

## State image
The state image contains the private signing key, which is generated when a built image is pushed to a container registry for the first time. It is encrypted by using two SECRETS. One is generated by `build.py` and stored in your `sbs-config.json`. The other one is included in the SBS image.

Why do we need the state image?
You need it to recover the signing key and additional SBS internal states to build the image in a new SBS instance after the original instance is deleted or corrupted.

## How to get the state image

1. Get the state image locally.
```buildoutcfg
./build.py get-state-image --env <path>/sbs-config.json
```
There will be an encrypted file which will be downloaded in your current directory, similar to this:
```buildoutcfg
docker.io.<user_name>.sbs22.s390x-v0.1-60fd72e.2020-10-21_07-20-08.516797
```

2. You can also save the state image to IBM Cloud Object Storage (COS).

    1) You first create a bucket on IBM Cloud Object Storage.

    2) Add below parameters into `sbs-config.json`.

      ```buildoutcfg
      "COS_API_KEY_ID": "<your_cloud_apikey>",
      "COS_RESOURCE_CRN": "<your_cloud_resource_crn_id>",
      "COS_ENDPOINT": "<your_public_cos_endpoint>",
      "COS_AUTH_ENDPOINT": "https://iam.cloud.ibm.com/oidc/token",
      "STATE_BUCKET_NAME": "<your_bucket_name>",
      ```

      If you already have COS parameters for the manifest in `sbs-config.json`, add `STATE_BUCKET_NAME` only.

    3) Update the configuration.

      ```buildoutcfg
      ./build.py update --env <path>/sbs-config.json
      ```

    4) Save the state image to COS.

      ```buildoutcfg
      ./build.py get-state-image --env <path>/sbs-config.json {--state-bucket-name <your_bucket_name>}
      ```

      Use the `--state-bucket-name` option, if you want to override the parameter in `sbs-config.json` or you don't have one in the file.
      When you save the state image to COS, you still get meta data of the state image in a local file of the same name as the state image file.

## How to recover the state image
Complete the following steps:

1. Create a new SBS instance as mentioned in the section [Deploying the Secure Build Server](SBS-HPVScloud.md#deploying-the-secure-build-server), with the same secret that was used to get the state image, otherwise the post state image operation fails.

2. Map the Public IP address with the hostname provided for the server in /etc/hosts file.
```buildoutcfg
10.20.x.xx  abc.test.com
```

3. Check the status of SBS.
```buildoutcfg
./build.py status --env <path>/sbs-config.json
```
4. Post the state image.
```buildoutcfg
./build.py post-state-image --state-image docker.io.<user_name>.sbs22.s390x-v0.1-60fd72e.2020-10-21_07-20-08.516797 --env <path>/sbs-config.json
```
Use the `--state-image` option to specify the state image file you downloaded previously with the `get-state-image` command.

5. Update the configuration.
```buildoutcfg
./build.py update --env <path>/sbs-config.json
```

6. Now you can further build your image using build command. Eventually your Docker image will be pushed to same registry.
```buildoutcfg
./build.py build --env <path>/sbs-config.json
```

7. Check the build log and wait until the build operation is completed.
```buildoutcfg
./build.py log --log build --env <path>/sbs-config.json
```

8. Check the status of the container.
```buildoutcfg
./build.py status --env <path>/sbs-config.json
```

## How to recover the state image from Cloud Object Storage
Complete the following steps:  

1. Create a new SBS server as mentioned in the section [Deploying the Secure Build Server](SBS-HPVScloud.md#deploying-the-secure-build-server), and use the same secret that was used to get the state image, otherwise the post state image operation fails.

2. You can list the Hyper Protect Virtual Servers instances.
```buildoutcfg
ibmcloud hpvs instances
```
After the instance is up and running, you can see `Public IP address` in the instance list.

3. Map the Public IP address with the hostname provided for the server in /etc/hosts file.
```buildoutcfg
10.20.x.xx  abc.test.com
```

4. Check the status of SBS.
```buildoutcfg
./build.py status --env <path>/sbs-config.json
```

5. Use the same `sbs-config.json` file.

6. Initialize the configuration.
```buildoutcfg
./build.py init --env <path>/sbs-config.json
```

7. Post the state image.
```buildoutcfg
./build.py post-state-image --env <path>/sbs-config.json --name docker.io.<user_name>.sbs22.s390x-v0.1-60fd72e.2020-10-21_07-20-08.516797 {--state-bucket-name <your_bucket_name>}
```
Use the `--state-bucket-name` option, if you want to override the parameter in `sbs-config.json` or you don't have one in the file.
Use the `--name` option to specifiy the name of the state image on COS, which is the same as the name of the meta data file you downloaded with the `get-state-image` command.

8. Update the configuration.
```buildoutcfg
./build.py update --env <path>/sbs-config.json
```
9. You can build your image using build command. Eventually your Docker image will be pushed to same registry.
```buildoutcfg
./build.py build --env <path>/sbs-config.json
```
10. Check the build log and wait until the build operation is completed.
```buildoutcfg
./build.py log --log build --env <path>/sbs-config.json
```
11. Check the status of SBS.
```buildoutcfg
./build.py status --env <path>/sbs-config.json
```

## How to stop and clean up a build process
SBS can take one build task at a time. If you want to start another build before an on-going
build completes successfully or prematurely with an error, you need to stop and clean up
the on-going build first.

1. You can always check the status of SBS using the `status` command.
```buildoutcfg
./build.py status --env <path>/sbs-config.json
```

2. Clean up SBS if you want to run another build without waiting for an on-going build to complete.
```buildoutcfg
./build.py clean --env <path>/sbs-config.json
```

3. Check the status again.
```buildoutcfg
./build.py status --env <path>/sbs-config.json
```
After the `clean` command completes successfully, the `status` command should return `restarted cicd`. This indicates the build service (cicd)
has been restarted and is ready to accept a new `build` command.
```
{
...
    "status": "restarted cicd"
}
```

## How to change the SECRET to a randomly generated NEW_SECRET
Complete the following steps:  

1. You can always update the secret to a new one in the `sbs-config.json` file. To update the secret, run the following command.
```buildoutcfg
./build.py update --env <path>/sbs-config.json --new-secret
```
`SECRET` will be updated with a randomly generated base64 value in the `sbs-config.json` file if the update operation is successful.

Note: After the secret is updated, you cannot use a state image obtained using the previous one. Consider obtaining a state image again with the new secret.


## Updating the Secure Build Server instance to the latest image

You can skip steps 1 to 4, when updating from SBS version 1.3.0.9 to 1.3.0.10.

1. Export the state image as mentioned in the section [How to get the state image](SBS-HPVScloud.md#how-to-get-the-state-image). This is to ensure that you have a backup.

2. Modify the `sbs-config.json` file for 1.3.0.10 according to the following instructions:
   1. Delete the `UUID` parameter.
   2. Add the `HOSTNAME`parameter.
   3. Delete the `CICD_PUBLIC_IP ` parameter.
   4. Ensure that you do not remove or change the `SECRET`.

3. Use build.py to create certificate-authority (CA) and client certificates which are used for secure communication from your client script to the SBS instance.
```buildoutcfg
./build.py create-client-cert --env <path>/sbs-config.json
```

4. Use build.py to create the server certificate signed by the CA certificate that was generated in the previous step. It will be setup on the server for secure communication.
```buildoutcfg
./build.py create-server-cert --env <path>/sbs-config.json
```

5. Get the environment key value pair to be used in instance-create command by running the following command.
```buildoutcfg
./build.py instance-env --env <path>/sbs-config.json
```

6. Update the instance
```buildoutcfg
ibmcloud hpvs instance-update SBContainer -i 1.3.0.9 --rd-path "secure_build.asc" --hostname="sbs.example.com" -e CLIENT_CRT=... -e CLIENT_CA=... -e SERVER_CRT=... -e SERVER_KEY=...
```

Note:
   * For the `HOSTNAME` parameter, use the value that was provided for HOSTNAME in the sbs-config.json file.
   * Use the repository definition file from [step 2](https://cloud.ibm.com/docs/hp-virtual-servers?topic=hp-virtual-servers-imagebuild#deploysecurebuild).

7. To check the status of the update process, run the following command.
```buildoutcfg
ibmcloud hpvs instance
```
The following is an example of the output.
```
Name                  SBSContainer
CRN                   crn:v1:staging:public:hpvs:dal13:a/1075962b93044362a562c8deebbfba2e:0b2df6e9-ec2c-4b4a-87dd-60f53f6a2a0d::
Location              dal13
Cloud tags
Cloud state           active
Server status         running
Plan                  Free
Public IP address     52.116.29.50
Internal IP address   172.17.151.218
Boot disk             25 GiB
Data disk             25 GiB
Memory                2048 MiB
Processors            1 vCPUs
Image type            self-provided
Image OS              self-defined
Image name            de.icr.io/zaas-hpvsop-prod/secure-docker-build:1.3.0.10
Environment           CLIENT_CA=...
                      CLIENT_CRT=...
                      SERVER_CRT=...
                      SERVER_KEY=...
Last operation        update succeeded
Last image update     2023-04-21 05:13
Created               2023-04-21
```

8. Update the following parameters of the `sbs-config.json` configuration file:
   - "build_image_tag": "1.3.0.10" 
   - "RUNTIME_TYPE": "classic"  Note that this parameter is only needed when you upgrade the instance from 1.3.0.8 or earlier to 1.3.0.10.
   - If the base image used in Docker file is Red Hat Simple Signed on IBM Cloud Container Registry, you must provide the 'ICR_BASE_REPO', and 'ICR_BASE_REPO_PUBLIC_KEY' parameters.
   - If the built image is pushed to IBM Cloud Container Registry, set "DOCKER_CONTENT_TRUST_PUSH_SERVER": "https://<domain_name>".

9. Update the SBS instance by running the following command:
   ```buildoutcfg
   ./build.py update --env <path>/sbs-config.json
   ```

### Note: To bring up the SBS Container on IBM Cloud Hyper Protect Virtual Servers for VPC (HPVS for VPC), follow the instructions in [this](SBS-VPC.md) document.  
