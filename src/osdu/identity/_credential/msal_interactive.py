# -----------------------------------------------------------------------------
# Copyright (c) Equinor ASA. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# -----------------------------------------------------------------------------
"""Base client for authentication and communicating with OSDU."""

import logging
import os
from abc import abstractmethod
import msal
import requests

from .base import OsduBaseCredential


logger = logging.getLogger(__name__)


class OsduMsalInteractiveCredentialBase(OsduBaseCredential):
    """Refresh token based client for connecting with OSDU."""

    # __access_token_expire_date = None
    __access_token = None
    # __id_token = None

    @property
    def client_id(self) -> str:
        """Client id used for authorisation

        Returns:
            str: client id
        """
        return self._client_id

    @property
    def authority(self) -> str:
        """Authority url for obtaining token

        Returns:
            str: authority url
        """
        return self._authority

    @property
    def scopes(self) -> str:
        """The current scopes requested

        Returns:
            str: scopes
        """
        return self._scopes

    @property
    def token_cache(self) -> str:
        """Path to persist tokens to

        Returns:
            str: token cache path
        """
        return self._token_cache

    # pylint: disable=too-many-arguments
    def __init__(
            self, client_id: str, authority: str, scopes: str, token_cache: str = None):
        """Setup the new client

        Args:
            client_id (str): client id for connecting
            authority (str): authority url
            scopes (str): scopes to request
            token_cache (str): path to persist tokens to
        """
        super().__init__()
        self._client_id = client_id
        self._authority = authority
        self._scopes = scopes
        self._token_cache = token_cache

    def get_token(self, **kwargs) -> str:
        """
        Check expiration date and return access_token.
        """
        # if datetime.now().timestamp() > self.__access_token_expire_date:
        self.refresh_access_token()
        return self.__access_token

    @abstractmethod
    def _auth_flow(self, app) -> dict:
        """Interactive flow for getting token. Auth code flow or device code flow

        Parameters
        ----------
        app : msal.PublicClientApplication

        Returns
        -------
        dict: Dictionary representing the returned token
        """

    def _refresh_access_token(self) -> dict:
        """Refresh token using msal.

        Returns:
            dict: Dictionary representing the returned token
        """

        # Create a preferably long-lived app instance which maintains a persistant token cache.
        cache = msal.SerializableTokenCache()
        if os.path.exists(self._token_cache):
            with open(self._token_cache, "r", encoding="utf8") as cachefile:
                cache.deserialize(cachefile.read())

        app = msal.PublicClientApplication(
            self._client_id, authority=self._authority, token_cache=cache
        )

        result = None
        # Firstly, check the cache to see if this end user has signed in before
        # accounts = app.get_accounts(username=config.get("username"))
        accounts = app.get_accounts()

        if accounts:
            logger.debug("Account(s) exists in cache, probably with token too. Let's try.")
            # for a in accounts:
            #     print(a["username"])
            chosen = accounts[
                0
            ]  # Assuming the end user chose this one to proceed - should change if multiple
            # Now let's try to find a token in cache for this account
            result = app.acquire_token_silent([self._scopes], account=chosen)

        if not result:
            logger.debug("No suitable token exists in cache. Let's get a new one from AAD.")

            print("A local browser window will be open for you to sign in. CTRL+C to cancel.")
            result = self._auth_flow(app)

            if cache.has_state_changed:
                with open(self.token_cache, "w", encoding="utf8") as cachefile:
                    cachefile.write(cache.serialize())

        return result

    def refresh_access_token(self) -> dict:
        """Refresh from refresh token.

        Returns:
            dict: Dictionary representing the returned token
        """
        # for i in range(self.retries + 1):
        #     # try several times if there any error
        #     try:
        #         result = self._refresh_access_token(
        #             self._token_endpoint, self._refresh_token, self._client_id, self._client_secret)
        #         break
        #     except HTTPError:
        #         if i == self._retries - 1:
        #             # too many errors, raise original exception
        #             raise
        result = self._refresh_access_token()

        if "preferred_username" in result:
            # TO DO: Save username for later login
            pass

        if "access_token" in result:
            # self.__id_token = result["id_token"]
            self.__access_token = result["access_token"]
            # self.__expire_date = datetime.now().timestamp() + result["expires_in"]

            # logger.info("Token is refreshed.")
        else:
            print(result.get("error"))
            print(result.get("error_description"))
            print(result.get("correlation_id"))

        return result  # You may need this when reporting a bug


class OsduMsalInteractiveCredential(OsduMsalInteractiveCredentialBase):
    """MSAL Interactive Auth code flow."""

    def _auth_flow(self, app) -> dict:
        return app.acquire_token_interactive(
            [self._scopes],
            timeout=10,
            # login_hint=config.get("username"),  # Optional.
            # If you know the username ahead of time, this parameter can pre-fill
            # the username (or email address) field of the sign-in page for the user,
            # Often, apps use this parameter during reauthentication,
            # after already extracting the username from an earlier sign-in
            # by using the preferred_username claim from returned id_token_claims.
            # Or simply "select_account" as below - Optional. It forces to show account selector page
            prompt=msal.Prompt.SELECT_ACCOUNT,
        )


class OsduMsalDeviceCode(OsduMsalInteractiveCredentialBase):
    """MSAL Interactive device code flow."""

    def _auth_flow(self, app) -> dict:
        print("device code flow")
        print(self._scopes)
        flow = app.initiate_device_flow(scopes=[self._scopes])
        if "user_code" not in flow:
            print("Failed to get user code for device code flow")
            print(flow)
        print(f'Visit https://microsoft.com/devicelogin and enter {flow["user_code"]}')
        return app.acquire_token_by_device_flow(flow)


class OsduMsalOnBehalfOf(OsduBaseCredential):
    # pylint: disable=too-many-arguments
    def __init__(
            self, interactive_client: OsduMsalInteractiveCredential | OsduMsalDeviceCode,
            client_secret: str, osdu_resource_id: str):
        """Setup the new client

        Args:
            client_id (str): client id for connecting
            authority (str): authority url
            scopes (str): scopes to request
            token_cache (str): path to persist tokens to
        """
        super().__init__()
        self._interactive_client = interactive_client
        self._client_secret = client_secret
        self._osdu_resource_id = osdu_resource_id

    @property
    def _user_impersonation_scope(self) -> str:
        return f"api://{self._osdu_resource_id}/user_impersonation"

    def _get_middle_tier_token(self) -> str:
        return self._interactive_client.get_token()

    def get_token(self, **kwargs) -> str:
        conf = {
            "grant_type": 'urn:ietf:params:oauth:grant-type:jwt-bearer',
            "assertion": self._get_middle_tier_token(),
            "client_id": self._interactive_client.client_id,
            "client_secret": self._client_secret,
            "resource": self._osdu_resource_id,
            "requested_token_use": 'on_behalf_of',
            "scope": 'openid user_impersonation'
        }
        res = requests.post(f"{self._interactive_client.authority}/oauth2/token", conf)
        if res.status_code != 200:
            print(res.text)
        return res.json()["access_token"]
