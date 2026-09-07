import os
import time
import requests

from dotenv import load_dotenv


load_dotenv()


BASE_URL = "https://nebula.saltoapis.com/v1"

INSTALLATION_ID = os.getenv("INSTALLATION_ID")
TOKEN = os.getenv("SALTO_TOKEN")


class SaltoAPI:

    def __init__(
        self,
        token=None,
        installation_id=None
    ):

        # -----------------------------------------------------
        # Si no se pasan por parámetro (ej. desde la GUI),
        # se usan los valores del .env cargados arriba.
        # -----------------------------------------------------

        token = token or TOKEN
        installation_id = installation_id or INSTALLATION_ID

        if not token:
            raise RuntimeError(
                "SALTO_TOKEN no está definido"
            )

        if not installation_id:
            raise RuntimeError(
                "INSTALLATION_ID no está definido"
            )

        self.installation_id = installation_id

        self.session = requests.Session()

        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        })

    # =========================================================
    # REQUEST NORMAL
    # =========================================================

    def _request(
        self,
        method,
        endpoint,
        **kwargs
    ):

        url = f"{BASE_URL}{endpoint}"

        response = self.session.request(
            method,
            url,
            timeout=30,
            **kwargs
        )

        if not response.ok:

            print("\nERROR SALTO")
            print(f"{method} {url}")
            print(f"Status: {response.status_code}")
            print(response.text)

            response.raise_for_status()

        if not response.content:
            return {}

        return response.json()

    # =========================================================
    # REQUEST CON REINTENTOS PARA ETAG
    # =========================================================

    def _request_with_retry(
        self,
        method,
        endpoint,
        max_retries=5,
        **kwargs
    ):

        for attempt in range(max_retries):

            try:

                return self._request(
                    method,
                    endpoint,
                    **kwargs
                )

            except requests.exceptions.HTTPError as e:

                response = e.response

                # -------------------------------------------------
                # SOLO REINTENTAMOS EL 409 DE ETAG
                # -------------------------------------------------

                if (
                    response is not None
                    and response.status_code == 409
                    and "ETag mismatch" in response.text
                ):

                    if attempt == max_retries - 1:

                        print(
                            "Se agotaron los reintentos "
                            "por conflicto ETag."
                        )

                        raise

                    wait_time = 1 + attempt

                    print(
                        f"ETag ocupado/modificado. "
                        f"Reintentando en "
                        f"{wait_time}s "
                        f"({attempt + 1}/{max_retries})..."
                    )

                    time.sleep(wait_time)

                else:

                    raise

    # =========================================================
    # UNITS
    # =========================================================

    def create_unit(
        self,
        name,
        privacy
    ):

        endpoint = (
            f"/installations/"
            f"{self.installation_id}/units"
        )

        payload = {
            "display_name": name,
            "privacy_settings": {
                "enabled": privacy
            }
        }

        return self._request(
            "POST",
            endpoint,
            json=payload
        )

    # =========================================================
    # LIST UNITS
    # =========================================================

    def list_units(self):

        endpoint = (
            f"/installations/"
            f"{self.installation_id}/units"
        )

        units = []
        page_token = None

        while True:

            params = {
                "page_size": 1000
            }

            if page_token:
                params["page_token"] = page_token

            response = self._request(
                "GET",
                endpoint,
                params=params
            )

            units.extend(
                response.get(
                    "units",
                    []
                )
            )

            page_token = response.get(
                "next_page_token"
            )

            if not page_token:
                break

        return units

    # =========================================================
    # DELETE UNIT
    # =========================================================

    def delete_unit(
        self,
        unit_name
    ):

        endpoint = f"/{unit_name}"

        return self._request(
            "DELETE",
            endpoint
        )

    # =========================================================
    # UPDATE UNIT PRIVACY
    # =========================================================

    def update_unit_privacy(
        self,
        unit_name,
        display_name,
        enabled
    ):

        endpoint = f"/{unit_name}"

        payload = {
            "privacy_settings": {
                "enabled": enabled
            },
            "display_name": display_name
        }

        return self._request_with_retry(
            "PATCH",
            endpoint,
            json=payload
        )

    # =========================================================
    # LIST USERS DE UNA UNIT
    # =========================================================

    def list_users(self, unit_name):

        endpoint = f"/{unit_name}/users"

        users = []
        page_token = None

        while True:

            params = {
                "page_size": 1000
            }

            if page_token:
                params["page_token"] = page_token

            response = self._request(
                "GET",
                endpoint,
                params=params
            )

            users.extend(
                response.get(
                    "users",
                    []
                )
            )

            page_token = response.get(
                "next_page_token"
            )

            if not page_token:
                break

        return users

    # =========================================================
    # LIST ACCESS RIGHTS DE UNA UNIT
    # =========================================================

    def list_access_rights(self, unit_name):

        endpoint = f"/{unit_name}/access-rights"

        access_rights = []
        page_token = None

        while True:

            params = {
                "page_size": 1000
            }

            if page_token:
                params["page_token"] = page_token

            response = self._request(
                "GET",
                endpoint,
                params=params
            )

            access_rights.extend(
                response.get(
                    "access_rights",
                    []
                )
            )

            page_token = response.get(
                "next_page_token"
            )

            if not page_token:
                break

        return access_rights

    # =========================================================
    # LIST / DELETE USER ACCESS RIGHTS (accesos YA asignados
    # a un usuario concreto)
    # =========================================================

    def list_user_access_rights(self, user_name):

        endpoint = f"/{user_name}/access-rights"

        rights = []
        page_token = None

        while True:

            params = {
                "page_size": 1000
            }

            if page_token:
                params["page_token"] = page_token

            response = self._request(
                "GET",
                endpoint,
                params=params
            )

            rights.extend(
                response.get(
                    "user_access_rights",
                    []
                )
            )

            page_token = response.get(
                "next_page_token"
            )

            if not page_token:
                break

        return rights

    def delete_user_access_right(
        self,
        user_access_right_name
    ):

        endpoint = f"/{user_access_right_name}"

        return self._request_with_retry(
            "DELETE",
            endpoint
        )

    # =========================================================
    # ACCESS POINT GROUPS
    # =========================================================

    def get_access_point_groups(self):

        endpoint = (
            f"/installations/"
            f"{self.installation_id}"
            f"/access-point-groups"
        )

        return self._request(
            "GET",
            endpoint,
            params={
                "page_size": 1000
            }
        )

    # =========================================================
    # ACCESS RIGHTS
    # =========================================================

    def create_access_right(
        self,
        unit_name,
        display_name,
        days,
        start_hour,
        start_minute,
        end_hour,
        end_minute
    ):

        endpoint = (
            f"/{unit_name}/access-rights"
        )

        payload = {
            "display_name": display_name,
            "schedules": [
                {
                    "days": [
                        {
                            "day_type": "NORMAL",
                            "day_of_week": day
                        }
                        for day in days
                    ],
                    "start_time": {
                        "hours": start_hour,
                        "minutes": start_minute,
                        "seconds": 0,
                        "nanos": 0
                    },
                    "end_time": {
                        "hours": end_hour,
                        "minutes": end_minute,
                        "seconds": 0,
                        "nanos": 0
                    }
                }
            ]
        }

        return self._request(
            "POST",
            endpoint,
            json=payload
        )

    # =========================================================
    # ATTACH ACCESS POINT GROUP
    # =========================================================

    def attach_group_to_access_right(
        self,
        access_right_name,
        group_name
    ):

        endpoint = (
            f"/{access_right_name}"
            f"/access-point-groups"
        )

        payload = {
            "access_point_group": group_name
        }

        return self._request(
            "POST",
            endpoint,
            json=payload
        )

    # =========================================================
    # USERS
    # =========================================================

    def create_user(
        self,
        unit_name,
        given_name,
        family_name,
        email,
        role,
        activate_time=None,
        expire_time=None
    ):

        endpoint = f"/{unit_name}/users"

        iam_roles = {
            "user": "iam-roles/unit.user",
            "admin": "iam-roles/unit.admin"
        }

        iam_role = iam_roles.get(
            role.lower(),
            "iam-roles/unit.user"
        )

        payload = {
            "name": unit_name,
            "given_name": given_name,
            "family_name": family_name,
            "email": email,
            "iam_roles": [
                iam_role
            ]
        }

        # -----------------------------------------------------
        # ACTIVATION / EXPIRATION
        # -----------------------------------------------------

        if activate_time:
            payload["activate_time"] = activate_time

        if expire_time:
            payload["expire_time"] = expire_time

        return self._request(
            "POST",
            endpoint,
            json=payload
        )

    # =========================================================
    # USER ACCESS RIGHT
    # =========================================================

    def assign_access_right(
        self,
        user_name,
        access_right_name
    ):

        endpoint = (
            f"/{user_name}/access-rights"
        )

        payload = {
            "access_right": access_right_name
        }

        return self._request_with_retry(
            "POST",
            endpoint,
            json=payload
        )

    # =========================================================
    # CARD KEY
    # =========================================================

    def assign_card_key(
        self,
        user_name,
        card_uid
    ):

        endpoint = (
            f"/{user_name}/card-key:assign"
        )

        payload = {
            "name": user_name,
            "uid": card_uid
        }

        return self._request_with_retry(
            "POST",
            endpoint,
            json=payload
        )

    # =========================================================
    # APP KEY
    # =========================================================

    def assign_app_key(
        self,
        user_name
    ):

        endpoint = (
            f"/{user_name}/app-key:assign"
        )

        return self._request_with_retry(
            "POST",
            endpoint
        )

    # =========================================================
    # PASSCODE
    # =========================================================

    def assign_passcode(
        self,
        user_name
    ):

        endpoint = (
            f"/{user_name}/passcode:assign"
        )

        return self._request_with_retry(
            "POST",
            endpoint
        )