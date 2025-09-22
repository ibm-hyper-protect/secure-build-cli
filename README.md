# IBM Cloud Hyper Protect Virtual Servers Secure Build Server

By using Hyper Protect Secure Build (HPSB), you can build a trusted container image within a secure enclave that is provided by IBM Cloud Hyper Protect Virtual Servers for VPC (HPVS for VPC). The enclave is highly isolated, where developers can access the container only by using a specific API and the cloud administrator cannot access the contents of the container. Therefore, the image that is built can be highly trusted. Specifically, the build server cryptographically signs the image, and a manifest (which is a collection of materials that are used during the build, for audit purposes). Since the enclave protects the signing keys within the enclave, the signatures can be used to verify whether the image and manifest are from the build server, and not elsewhere.


* To setup and use HPSB in IBM Cloud Hyper Protect Virtual Servers for VPC, see [HPSB Deployment on HPVS for VPC](HPSB-VPC.md).

* To setup and use HPSB in IBM Hyper Protect Virtual Servers for Gen-2 On-Prem, see [this topic](https://www.ibm.com/docs/en/hpvs/2.2.x?topic=building-your-applications-hyper-protect-secure-build).

**Note:** It is recommend that you use IBM Cloud Hyper Protect Virtual Servers for VPC, which is the next generation of IBM Cloud Hyper Protect Virtual Servers that offers an hourly billing, and improved logging support, beside other benefits.

## License

[Apache 2.0](https://github.com/ibm-hyper-protect/secure-build-cli/blob/main/LICENSE)

## Contributor License Agreement (CLA)

To contribute to the secure-build-cli project, it is required to sign the
[individual CLA form](https://gist.github.com/moriohara/6ecc6cca48f4c018160e35ebd4e0eb8a)
if you're contributing as an individual, or
[corporate CLA form](https://gist.github.com/moriohara/e2ad4706f1142089c181d1583f8e6883)
if you're contributing as part of your job.

You are required to do this only once online with [cla-assistant](https://github.com/cla-assistant/cla-assistant) when a pull request is created, and then you are free to contribute to the secure-build-cli project.
