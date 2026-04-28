"""
ModelServe AWS infrastructure.
Single EC2 + Docker Compose topology.
Region: ap-southeast-1
"""

from __future__ import annotations

import json

import pulumi
import pulumi_aws as aws

REGION = "ap-southeast-1"
AZ = "ap-southeast-1a"
PROJECT_TAG = {"Project": "modelserve"}


def tags(extra: dict | None = None) -> dict:
    out = dict(PROJECT_TAG)
    if extra:
        out.update(extra)
    return out


cfg = pulumi.Config()
ssh_public_key = cfg.require("sshPublicKey")

provider = aws.Provider(
    "aws",
    region=REGION,
)

invoke_opts = pulumi.InvokeOptions(provider=provider)
caller = aws.get_caller_identity_output(opts=invoke_opts)

ubuntu_ami = aws.ec2.get_ami(
    most_recent=True,
    owners=["099720109477"],
    filters=[
        aws.ec2.GetAmiFilterArgs(
            name="name",
            values=["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"],
        ),
        aws.ec2.GetAmiFilterArgs(name="virtualization-type", values=["hvm"]),
    ],
    opts=invoke_opts,
)

vpc = aws.ec2.Vpc(
    "modelserve-vpc",
    cidr_block="10.0.0.0/16",
    enable_dns_hostnames=True,
    enable_dns_support=True,
    tags=tags({"Name": "modelserve-vpc"}),
    opts=pulumi.ResourceOptions(provider=provider),
)

igw = aws.ec2.InternetGateway(
    "modelserve-igw",
    vpc_id=vpc.id,
    tags=tags({"Name": "modelserve-igw"}),
    opts=pulumi.ResourceOptions(provider=provider),
)

subnet = aws.ec2.Subnet(
    "modelserve-public-subnet",
    vpc_id=vpc.id,
    cidr_block="10.0.1.0/24",
    availability_zone=AZ,
    map_public_ip_on_launch=True,
    tags=tags({"Name": "modelserve-public-subnet"}),
    opts=pulumi.ResourceOptions(provider=provider),
)

rtb = aws.ec2.RouteTable(
    "modelserve-public-rt",
    vpc_id=vpc.id,
    tags=tags({"Name": "modelserve-public-rt"}),
    opts=pulumi.ResourceOptions(provider=provider),
)

aws.ec2.Route(
    "modelserve-default-route",
    route_table_id=rtb.id,
    destination_cidr_block="0.0.0.0/0",
    gateway_id=igw.id,
    opts=pulumi.ResourceOptions(provider=provider),
)

aws.ec2.RouteTableAssociation(
    "modelserve-rta",
    subnet_id=subnet.id,
    route_table_id=rtb.id,
    opts=pulumi.ResourceOptions(provider=provider),
)

ssh_key = aws.ec2.KeyPair(
    "modelserve-keypair",
    public_key=ssh_public_key,
    tags=tags({"Name": "modelserve-keypair"}),
    opts=pulumi.ResourceOptions(provider=provider),
)

sg = aws.ec2.SecurityGroup(
    "modelserve-sg",
    vpc_id=vpc.id,
    description="ModelServe capstone - SSH and app ports only",
    egress=[
        aws.ec2.SecurityGroupEgressArgs(
            protocol="-1",
            from_port=0,
            to_port=0,
            cidr_blocks=["0.0.0.0/0"],
            description="All outbound",
        )
    ],
    ingress=[
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=p,
            to_port=p,
            cidr_blocks=["0.0.0.0/0"],
            description=f"TCP {p}",
        )
        for p in (22, 8000, 3001, 5000, 9090)
    ],
    tags=tags({"Name": "modelserve-sg"}),
    opts=pulumi.ResourceOptions(provider=provider),
)

_stack_safe = pulumi.get_stack().lower().replace("_", "-")
bucket_name = caller.account_id.apply(
    lambda aid: f"modelserve-{_stack_safe}-{aid}-artifacts"[:63]
)

artifacts_bucket = aws.s3.Bucket(
    "modelserve-artifacts",
    bucket=bucket_name,
    force_destroy=True,
    tags=tags({"Name": "modelserve-artifacts"}),
    opts=pulumi.ResourceOptions(provider=provider),
)

ecr_api = aws.ecr.Repository(
    "modelserve-api",
    name="modelserve-api",
    force_delete=True,
    image_tag_mutability="MUTABLE",
    tags=tags({"Name": "modelserve-api"}),
    opts=pulumi.ResourceOptions(provider=provider),
)

ecr_mlflow = aws.ecr.Repository(
    "modelserve-mlflow",
    name="modelserve-mlflow",
    force_delete=True,
    image_tag_mutability="MUTABLE",
    tags=tags({"Name": "modelserve-mlflow"}),
    opts=pulumi.ResourceOptions(provider=provider),
)

assume_role = aws.iam.get_policy_document(
    statements=[
        aws.iam.GetPolicyDocumentStatementArgs(
            actions=["sts:AssumeRole"],
            principals=[
                aws.iam.GetPolicyDocumentStatementPrincipalArgs(
                    type="Service",
                    identifiers=["ec2.amazonaws.com"],
                )
            ],
        )
    ],
    opts=invoke_opts,
)

ec2_role = aws.iam.Role(
    "modelserve-ec2-role",
    name="modelserve-ec2-role",
    assume_role_policy=assume_role.json,
    tags=tags({"Name": "modelserve-ec2-role"}),
    opts=pulumi.ResourceOptions(provider=provider),
)

ec2_policy_doc = pulumi.Output.all(
    artifacts_bucket.arn,
    ecr_api.arn,
    ecr_mlflow.arn,
).apply(
    lambda args: json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObject",
                        "s3:PutObject",
                        "s3:ListBucket",
                        "s3:DeleteObject",
                    ],
                    "Resource": [args[0], f"{args[0]}/*"],
                },
                {
                    "Effect": "Allow",
                    "Action": ["ecr:GetAuthorizationToken"],
                    "Resource": "*",
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "ecr:BatchCheckLayerAvailability",
                        "ecr:GetDownloadUrlForLayer",
                        "ecr:BatchGetImage",
                        "ecr:PutImage",
                        "ecr:InitiateLayerUpload",
                        "ecr:UploadLayerPart",
                        "ecr:CompleteLayerUpload",
                    ],
                    "Resource": [args[1], args[2]],
                },
            ],
        }
    )
)

aws.iam.RolePolicy(
    "modelserve-ec2-inline",
    name="modelserve-ec2-inline",
    role=ec2_role.id,
    policy=ec2_policy_doc,
    opts=pulumi.ResourceOptions(provider=provider),
)

instance_profile = aws.iam.InstanceProfile(
    "modelserve-ec2-profile",
    name="modelserve-ec2-profile",
    role=ec2_role.name,
    opts=pulumi.ResourceOptions(provider=provider),
)

USER_DATA = r"""#!/bin/bash
set -euxo pipefail

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y ca-certificates curl gnupg git unzip python3-venv python3-pip python-is-python3 awscli

install -m 0755 -d /etc/apt/keyrings

curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu jammy stable" \
  > /etc/apt/sources.list.d/docker.list

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

usermod -aG docker ubuntu || true

systemctl enable docker
systemctl start docker

touch /var/log/modelserve-bootstrap.done
"""

instance = aws.ec2.Instance(
    "modelserve-ec2",
    ami=ubuntu_ami.id,
    instance_type="t3.medium",
    subnet_id=subnet.id,
    vpc_security_group_ids=[sg.id],
    key_name=ssh_key.key_name,
    associate_public_ip_address=True,
    user_data=USER_DATA,
    user_data_replace_on_change=False,
    root_block_device=aws.ec2.InstanceRootBlockDeviceArgs(
        volume_type="gp3",
        volume_size=30,
        delete_on_termination=True,
    ),
    tags=tags({"Name": "modelserve-ec2"}),
    opts=pulumi.ResourceOptions(provider=provider),
)

eip = aws.ec2.Eip(
    "modelserve-eip",
    domain="vpc",
    tags=tags({"Name": "modelserve-eip"}),
    opts=pulumi.ResourceOptions(provider=provider),
)

aws.ec2.EipAssociation(
    "modelserve-eip-assoc",
    instance_id=instance.id,
    allocation_id=eip.id,
    opts=pulumi.ResourceOptions(provider=provider),
)

ml_inference_repo_url = pulumi.Output.concat(
    caller.account_id,
    ".dkr.ecr.",
    REGION,
    ".amazonaws.com/",
    ecr_api.name,
)

pulumi.export("vpc_id", vpc.id)
pulumi.export("subnet_id", subnet.id)
pulumi.export("security_group_id", sg.id)
pulumi.export("instance_id", instance.id)
pulumi.export("instance_public_ip", eip.public_ip)
pulumi.export("ml_inference_repo_url", ml_inference_repo_url)
pulumi.export("s3_bucket_name", artifacts_bucket.bucket)
pulumi.export("grafana_url", eip.public_ip.apply(lambda ip: f"http://{ip}:3001"))
pulumi.export("prometheus_url", eip.public_ip.apply(lambda ip: f"http://{ip}:9090"))
pulumi.export("mlflow_url", eip.public_ip.apply(lambda ip: f"http://{ip}:5000"))