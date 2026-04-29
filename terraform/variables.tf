variable "aws_region" {
  description = "AWS region for the IntelliBMS production stack."
  type        = string
  default     = "us-east-1"
}

variable "instance_name" {
  description = "Logical name for the IntelliBMS EC2 instance and related resources."
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type for the IntelliBMS host."
  type        = string
}

variable "ami_id" {
  description = "AMI ID currently used by the live EC2 instance. Required for import-first Terraform adoption."
  type        = string
}

variable "key_name" {
  description = "AWS EC2 key pair name attached to the instance."
  type        = string
}

variable "vpc_id" {
  description = "VPC ID that contains the IntelliBMS EC2 instance."
  type        = string
}

variable "subnet_id" {
  description = "Subnet ID where the IntelliBMS EC2 instance runs."
  type        = string
}

variable "allowed_ssh_cidr" {
  description = "Trusted CIDR block allowed to SSH into the EC2 host."
  type        = string
  default     = "203.0.113.10/32"
}

variable "domain_name" {
  description = "Public DNS name pointed at the IntelliBMS Elastic IP."
  type        = string
  default     = "intellibms.n8nautomations.me"
}

variable "root_volume_size_gb" {
  description = "Target size of the EC2 root EBS volume in GiB."
  type        = number
  default     = 30
}

variable "root_volume_type" {
  description = "EBS volume type for the EC2 root block device."
  type        = string
  default     = "gp3"
}

variable "cloudwatch_log_retention_days" {
  description = "Retention period for CloudWatch log groups."
  type        = number
  default     = 30
}

variable "project_tags" {
  description = "Additional tags applied to Terraform-managed resources."
  type        = map(string)
  default     = {}
}

variable "security_group_name" {
  description = "Optional explicit security group name. Set this to match the existing live SG before import if needed."
  type        = string
  default     = null
}

variable "security_group_description" {
  description = "Exact description of the existing security group to avoid replacement during import-first adoption."
  type        = string
}

variable "iam_role_name" {
  description = "Optional explicit IAM role name for the EC2 CloudWatch role."
  type        = string
  default     = null
}

variable "iam_instance_profile_name" {
  description = "Optional explicit IAM instance profile name for the EC2 host."
  type        = string
  default     = null
}

variable "enable_detailed_monitoring" {
  description = "Whether to enable detailed EC2 monitoring."
  type        = bool
  default     = false
}
