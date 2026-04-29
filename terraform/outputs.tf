output "instance_id" {
  description = "EC2 instance ID for the IntelliBMS host."
  value       = aws_instance.intellibms.id
}

output "instance_public_ip" {
  description = "Public IPv4 address currently attached to the IntelliBMS host."
  value       = aws_eip.intellibms.public_ip
}

output "instance_public_dns" {
  description = "Public DNS name of the IntelliBMS host."
  value       = aws_instance.intellibms.public_dns
}

output "security_group_id" {
  description = "Security group ID attached to the IntelliBMS EC2 host."
  value       = aws_security_group.intellibms.id
}

output "iam_instance_profile_name" {
  description = "IAM instance profile name attached to the EC2 host."
  value       = aws_iam_instance_profile.intellibms.name
}

output "cloudwatch_log_group_names" {
  description = "CloudWatch log group names managed for the IntelliBMS deployment."
  value       = { for key, group in aws_cloudwatch_log_group.intellibms : key => group.name }
}
