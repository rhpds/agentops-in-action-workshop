The Application schema fixture was exported from the installed
`applications.argoproj.io` v1alpha1 CRD on 2026-09-29. Descriptions and status
were removed. Refresh it when upgrading Argo CD, and review any new fields
against the admission guard's immutable-field checks.

The helper uses Kubernetes' OpenAPI-to-CEL type provider to compile Application
expressions, then evaluates the JSON cases dynamically. ObjectMeta and request
remain dynamic because the CRD does not describe their Kubernetes schemas.
Dynamic evaluation translates the escaped `__namespace__` field back to its
JSON key. A negative compilation check ensures structured objects cannot be iterated as
maps—the error that the previous dynamic-only tests missed.
