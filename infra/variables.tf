# ---------------------------------------------------------------------------
# Mandatory FinOps tagging variables
# All three values must be supplied at plan/apply time (no defaults) so that
# every cloud resource carries the tags required for cost allocation, incident
# attribution, and automated governance.
# ---------------------------------------------------------------------------

variable "tenant_id" {
  description = "Tenant identifier — propagated as the 'tenantId' tag on every resource."
  type        = string
}

variable "submission_id" {
  description = "Submission identifier — propagated as the 'submissionId' tag on every resource."
  type        = string
}

variable "cost_centre" {
  description = "Cost-centre code — propagated as the 'costCentre' tag on every resource."
  type        = string
}
