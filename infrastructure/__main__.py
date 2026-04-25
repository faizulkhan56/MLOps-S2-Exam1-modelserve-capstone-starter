# ============================================================================
# ModelServe — Pulumi Infrastructure
# ============================================================================
# TODO: Provision the AWS resources your deployment topology requires.
#
# Your topology is YOUR decision. Common resources include:
#
#   Networking:
#     - VPC with a CIDR block
#     - Public subnet in an availability zone
#     - Internet gateway
#     - Route table with a default route to the internet gateway
#     - Route table association with the subnet
#
#   Security:
#     - Security group with ingress rules for your service ports
#     - Security group egress rule allowing all outbound traffic
#     - Consider: which ports actually need to be open? To whom?
#
#   Compute (if deploying to EC2):
#     - EC2 instance with appropriate instance type
#     - Key pair for SSH access
#     - Elastic IP for a stable address
#     - IAM instance profile + role with S3 and ECR permissions
#     - User-data script to install Docker and Docker Compose on boot
#
#   Storage:
#     - S3 bucket for MLflow artifacts and/or Feast offline store
#     - ECR repository for your Docker images (set force_delete=True)
#
# Requirements:
#   - All resources MUST be tagged with: Project = "modelserve"
#   - Export stack outputs for use by CI/CD (IPs, URLs, bucket names)
#   - pulumi destroy must cleanly remove everything
#   - Use os.environ.get("SSH_PUBLIC_KEY", "") for the key pair
#
# Refer to the Pulumi/CI/CD lab from Episodes 2-3 for patterns.
# ============================================================================
