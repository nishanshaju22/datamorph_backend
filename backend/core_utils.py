from rest_framework.exceptions import ValidationError

CLIENT_ID_HEADER = "HTTP_X_CLIENT_ID"  # corresponds to "X-Client-Id" header


def get_client_id(request) -> str:
    """
    Return the client-provided identifier sent via the 'X-Client-Id' header.
    """
    client_id = request.META.get(CLIENT_ID_HEADER, "").strip()

    if not client_id:
        raise ValidationError(
            "Missing X-Client-Id header. The frontend must send a client id "
            "with every request."
        )

    if len(client_id) > 64:
        raise ValidationError("X-Client-Id header is invalid.")

    return client_id