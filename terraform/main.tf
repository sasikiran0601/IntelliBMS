locals {
  common_tags = merge(
    {
      Project     = "IntelliBMS"
      Environment = "production"
      ManagedBy   = "Terraform"
      Service     = "battery-monitoring"
    },
    var.project_tags,
  )

  security_group_name      = coalesce(var.security_group_name, "${var.instance_name}-sg")
  cloudwatch_role_name     = coalesce(var.iam_role_name, "${var.instance_name}-cloudwatch-role")
  instance_profile_name    = coalesce(var.iam_instance_profile_name, "${var.instance_name}-instance-profile")

  cloudwatch_log_groups = {
    app          = "/intellibms/app"
    nginx_access = "/intellibms/nginx/access"
    nginx_error  = "/intellibms/nginx/error"
    deploy       = "/intellibms/deploy"
  }
}

resource "aws_security_group" "intellibms" {
  name        = local.security_group_name
  description = var.security_group_description
  vpc_id      = var.vpc_id

  ingress {
    description = "SSH access for trusted operators"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }

  ingress {
    description = "Public HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Public HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name      = local.security_group_name
    Component = "network"
  })
}

resource "aws_iam_role" "intellibms_cloudwatch" {
  name = local.cloudwatch_role_name

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name      = local.cloudwatch_role_name
    Component = "iam"
  })
}

resource "aws_iam_role_policy_attachment" "cloudwatch_agent" {
  role       = aws_iam_role.intellibms_cloudwatch.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

resource "aws_iam_instance_profile" "intellibms" {
  name = local.instance_profile_name
  role = aws_iam_role.intellibms_cloudwatch.name

  tags = merge(local.common_tags, {
    Name      = local.instance_profile_name
    Component = "iam"
  })
}

resource "aws_cloudwatch_log_group" "intellibms" {
  for_each = local.cloudwatch_log_groups

  name              = each.value
  retention_in_days = var.cloudwatch_log_retention_days

  tags = merge(local.common_tags, {
    Name      = each.value
    Component = "logging"
  })
}

resource "aws_instance" "intellibms" {
  ami                         = var.ami_id
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  key_name                    = var.key_name
  vpc_security_group_ids      = [aws_security_group.intellibms.id]
  iam_instance_profile        = aws_iam_instance_profile.intellibms.name
  associate_public_ip_address = true
  monitoring                  = var.enable_detailed_monitoring

  root_block_device {
    volume_size           = var.root_volume_size_gb
    volume_type           = var.root_volume_type
    delete_on_termination = true
  }

  tags = merge(local.common_tags, {
    Name      = var.instance_name
    Component = "compute"
    Domain    = var.domain_name
  })

  lifecycle {
    ignore_changes = [
      ami,
      associate_public_ip_address,
      credit_specification,
      cpu_options,
      maintenance_options,
      metadata_options,
      private_dns_name_options,
      user_data,
      user_data_base64,
    ]
  }
}

resource "aws_eip" "intellibms" {
  domain   = "vpc"
  instance = aws_instance.intellibms.id

  tags = merge(local.common_tags, {
    Name      = "${var.instance_name}-eip"
    Component = "network"
    Domain    = var.domain_name
  })
}
