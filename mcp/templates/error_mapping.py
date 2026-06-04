"""
gRPC status code ↔ HTTP status code mapping template.

Provides canonical error mapping for gRPC services migrated from REST APIs.
"""

ERROR_MAPPING_TEMPLATE = """\
# gRPC ↔ HTTP Status Code Error Mapping
# =====================================================
# Use this table when implementing error-mapping interceptors
# or translating errors in REST gateway / gRPC-gateway adapters.

| gRPC Status Code         | HTTP Status Code | Description                                  |
|--------------------------|------------------|----------------------------------------------|
| OK                       | 200              | Success                                      |
| CANCELLED                | 499              | Client closed request                        |
| UNKNOWN                  | 500              | Unknown server error                         |
| INVALID_ARGUMENT         | 400              | Bad request / validation failure             |
| DEADLINE_EXCEEDED        | 504              | Gateway timeout                              |
| NOT_FOUND                | 404              | Resource not found                           |
| ALREADY_EXISTS           | 409              | Resource conflict / duplicate                |
| PERMISSION_DENIED        | 403              | Forbidden                                    |
| RESOURCE_EXHAUSTED       | 429              | Rate limit / quota exceeded                  |
| FAILED_PRECONDITION      | 400              | Operation rejected due to system state       |
| ABORTED                  | 409              | Concurrency conflict (e.g. optimistic lock)  |
| OUT_OF_RANGE             | 400              | Value outside valid range                    |
| UNIMPLEMENTED            | 501              | Method not implemented                       |
| INTERNAL                 | 500              | Internal server error                        |
| UNAVAILABLE              | 503              | Service unavailable / retry                  |
| DATA_LOSS                | 500              | Unrecoverable data corruption                |
| UNAUTHENTICATED          | 401              | Unauthorized / missing credentials           |

# Python helper — paste into your servicer implementations:
#
#   import grpc
#
#   HTTP_TO_GRPC = {
#       200: grpc.StatusCode.OK,
#       400: grpc.StatusCode.INVALID_ARGUMENT,
#       401: grpc.StatusCode.UNAUTHENTICATED,
#       403: grpc.StatusCode.PERMISSION_DENIED,
#       404: grpc.StatusCode.NOT_FOUND,
#       409: grpc.StatusCode.ALREADY_EXISTS,
#       429: grpc.StatusCode.RESOURCE_EXHAUSTED,
#       500: grpc.StatusCode.INTERNAL,
#       501: grpc.StatusCode.UNIMPLEMENTED,
#       503: grpc.StatusCode.UNAVAILABLE,
#       504: grpc.StatusCode.DEADLINE_EXCEEDED,
#   }
#
#   GRPC_TO_HTTP = {v: k for k, v in HTTP_TO_GRPC.items()}
"""

ERROR_MAPPING_DESCRIPTION = """\
Canonical gRPC ↔ HTTP status code mapping table for REST-to-gRPC migrations.

Includes:
- Full mapping table for all standard gRPC status codes
- Python dict snippets for both directions (HTTP→gRPC and gRPC→HTTP)
- Notes on special cases (ABORTED vs ALREADY_EXISTS, FAILED_PRECONDITION vs INVALID_ARGUMENT)
"""
