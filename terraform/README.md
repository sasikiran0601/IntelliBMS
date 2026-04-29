# Terraform Adoption Guide

This directory models the current live IntelliBMS AWS deployment and is designed for an **import-first** rollout.

## What Terraform Manages

Terraform in this repo is intended to manage:

- the EC2 instance that hosts IntelliBMS
- the EC2 security group
- the Elastic IP serving `intellibms.n8nautomations.me`
- the IAM role and instance profile used for CloudWatch access
- CloudWatch log groups for app, NGINX, and deployment logs

Terraform intentionally does **not** manage:

- `/opt/intellibms/docker-compose.yml`
- `/opt/intellibms/.env`
- `/opt/intellibms/nginx/nginx.conf`
- `/opt/intellibms/models/soh_model.h5`
- datasets
- SQLite contents in `/opt/intellibms/data`

## Recommended Workflow

1. Copy the example variables:

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

2. Fill `terraform.tfvars` with the live AWS values:

- current region
- current instance type
- live AMI ID
- key pair name
- VPC and subnet IDs
- trusted SSH CIDR
- domain name

3. Initialize and validate:

```bash
terraform init
terraform fmt -check
terraform validate
terraform plan
```

## Import-First Adoption

Use the following sequence to adopt the existing live stack.

### Required imports

```bash
terraform import aws_security_group.intellibms sg-xxxxxxxxxxxxxxxxx
terraform import aws_instance.intellibms i-xxxxxxxxxxxxxxxxx
terraform import aws_eip.intellibms eipalloc-xxxxxxxxxxxxxxxxx
```

### Optional imports if the IAM resources already exist

```bash
terraform import aws_iam_role.intellibms_cloudwatch existing-role-name
terraform import aws_iam_instance_profile.intellibms existing-instance-profile-name
```

### Optional imports if log groups already exist

```bash
terraform import 'aws_cloudwatch_log_group.intellibms["app"]' /intellibms/app
terraform import 'aws_cloudwatch_log_group.intellibms["nginx_access"]' /intellibms/nginx/access
terraform import 'aws_cloudwatch_log_group.intellibms["nginx_error"]' /intellibms/nginx/error
terraform import 'aws_cloudwatch_log_group.intellibms["deploy"]' /intellibms/deploy
```

After import, run:

```bash
terraform plan
```

Keep iterating on variables until the plan shows either no changes or only the changes you intentionally want, such as increasing the root volume size.

## Notes About The Live Environment

- The current deployment is still updated by GitHub Actions over SSH.
- Docker Compose, NGINX, and the runtime `.env` remain managed on the instance.
- The ML model is mounted from `/opt/intellibms/models/soh_model.h5`.
- The current root EBS volume is too small for repeated large Docker pulls, so `root_volume_size_gb = 30` is the recommended target.
