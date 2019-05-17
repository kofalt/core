import datetime
import requests
import json
import urllib
import urlparse

from xml.etree import ElementTree

from .apikeys import APIKey
from .. import config, util
from ..dao import dbutil

from ..web.errors import APIAuthProviderException, APIUnknownUserException, APIRefreshTokenException

log = config.log


class AuthProvider(object):
    """
    Abstract auth provider class
    """

    def __init__(self, auth_type, set_config=True):
        self.auth_type = auth_type
        if set_config:
            try:
                self.config = config.get_auth(auth_type)
            except KeyError:
                raise NotImplementedError("Auth type {} is not supported by this instance".format(auth_type))

    @staticmethod
    def factory(auth_type):
        """
        Factory method to aid in the creation of an AuthProvider instance
        when auth_type is dynamic.
        """
        if auth_type in AuthProviders:
            provider_class = AuthProviders[auth_type]
            return provider_class()
        else:
            raise NotImplementedError("Auth type {} is not supported".format(auth_type))

    def validate_code(self, code, **kwargs):
        raise NotImplementedError

    def ensure_user_exists(self, uid):
        user = config.db.users.find_one({"_id": uid})
        if not user:
            raise APIUnknownUserException("User {} will need to be added to the system before managing data.".format(uid))
        if user.get("disabled", False) is True:
            raise APIUnknownUserException("User {} is disabled.".format(uid))

    def set_user_gravatar(self, uid, email):
        """
        Looks for user gravatar via email. If a gravatar is found, adds to avatar map.
        If the user has not yet set an avatar (first time logging in), set the default
        avatar to the gravatar image.
        """
        if email and uid:
            gravatar = util.resolve_gravatar(email)
            if gravatar is not None:
                timestamp = datetime.datetime.utcnow()
                # Update the user's gravatar if it has changed.
                config.db.users.update_one({"_id": uid, "avatars.gravatar": {"$ne": gravatar}}, {"$set": {"avatars.gravatar": gravatar, "modified": timestamp}})
                # If the user has no avatar set, use gravar
                config.db.users.update_one({"_id": uid, "avatar": {"$exists": False}}, {"$set": {"avatar": gravatar, "modified": timestamp}})

    def set_refresh_token_if_exists(self, uid, refresh_token):
        # Also check to make sure if refresh token is missing, that the user
        # has a refresh token on their user doc. If not, alert the client.
        query = {"uid": uid, "auth_type": self.auth_type}
        if not refresh_token:
            token = config.db.refreshtokens.find_one(query)
            if not token:
                # user does not have refresh token, alert the client
                raise APIRefreshTokenException("invalid_refresh_token")
            else:
                # user does have a previously saved refresh token, move on
                return

        refresh_doc = {"token": refresh_token, "auth_type": self.auth_type, "uid": uid}
        dbutil.fault_tolerant_replace_one(config.db, "refreshtokens", query, refresh_doc, upsert=True)


class JWTAuthProvider(AuthProvider):
    def __init__(self):
        super(JWTAuthProvider, self).__init__("ldap")

    def validate_code(self, code, **kwargs):
        uid = self.validate_user(code)
        return {"access_token": code, "uid": uid, "auth_type": self.auth_type, "expires": datetime.datetime.utcnow() + datetime.timedelta(days=14)}

    def validate_user(self, token):
        r = requests.post(self.config["verify_endpoint"], data={"token": token}, verify=self.config.get("check_ssl", True))
        if not r.ok:
            raise APIAuthProviderException("User token not valid")
        uid = self._get_uid(json.loads(r.content))
        if not uid:
            raise APIAuthProviderException("Auth provider did not provide user email")

        self.ensure_user_exists(uid)
        self.set_user_gravatar(uid, uid)

        return uid

    def _get_uid(self, token_data):
        mail_format = self.config.get("mail_format")
        if mail_format:
            try:
                return mail_format.format(**token_data)
            except KeyError:
                return None
        return token_data.get("mail")


class GoogleOAuthProvider(AuthProvider):
    def __init__(self):
        super(GoogleOAuthProvider, self).__init__("google")

    def validate_code(self, code, **kwargs):
        payload = {"client_id": self.config["client_id"], "client_secret": self.config["client_secret"], "code": code, "grant_type": "authorization_code", "redirect_uri": config.get_item("site", "redirect_url")}

        r = requests.post(self.config["token_endpoint"], data=payload)
        if not r.ok:
            raise APIAuthProviderException("User code not valid")

        response = json.loads(r.content)
        token = response["access_token"]

        uid = self.validate_user(token)
        self.set_refresh_token_if_exists(uid, response.get("refresh_token"))

        return {"access_token": token, "uid": uid, "auth_type": self.auth_type, "expires": datetime.datetime.utcnow() + datetime.timedelta(seconds=response["expires_in"])}

    def refresh_token(self, token):
        payload = {"client_id": self.config["client_id"], "client_secret": self.config["client_secret"], "refresh_token": token, "grant_type": "refresh_token"}
        r = requests.post(self.config["refresh_endpoint"], data=payload)
        if not r.ok:
            raise APIAuthProviderException("Unable to refresh token.")

        response = json.loads(r.content)
        return {"access_token": response["access_token"], "expires": datetime.datetime.utcnow() + datetime.timedelta(seconds=response["expires_in"])}

    def validate_user(self, token):
        r = requests.get(self.config["id_endpoint"], headers={"Authorization": "Bearer " + token})
        if not r.ok:
            raise APIAuthProviderException("User token not valid")
        identity = json.loads(r.content)
        uid = identity.get("email")
        if not uid:
            raise APIAuthProviderException("Auth provider did not provide user email")

        self.ensure_user_exists(uid)
        self.set_user_gravatar(uid, uid)
        self.set_user_avatar(uid, identity)

        return uid

    def set_user_avatar(self, uid, identity):
        # A google-specific avatar URL is provided in the identity return.
        provider_avatar = identity.get("picture", "")

        # Remove attached size param from URL.
        u = urlparse.urlparse(provider_avatar)
        query = urlparse.parse_qs(u.query)
        query.pop("sz", None)
        u = u._replace(query=urllib.urlencode(query, True))
        provider_avatar = urlparse.urlunparse(u)

        timestamp = datetime.datetime.utcnow()
        # Update the user's provider avatar if it has changed.
        config.db.users.update_one({"_id": uid, "avatars.provider": {"$ne": provider_avatar}}, {"$set": {"avatars.provider": provider_avatar, "modified": timestamp}})
        # If the user has no avatar set, mark their provider_avatar as their chosen avatar.
        config.db.users.update_one({"_id": uid, "avatar": {"$exists": False}}, {"$set": {"avatar": provider_avatar, "modified": timestamp}})


class WechatOAuthProvider(AuthProvider):
    def __init__(self):
        super(WechatOAuthProvider, self).__init__("wechat")

    def validate_code(self, code, **kwargs):
        payload = {"appid": self.config["client_id"], "secret": self.config["client_secret"], "code": code, "grant_type": "authorization_code"}
        r = requests.post(self.config["token_endpoint"], params=payload)
        if not r.ok:
            raise APIAuthProviderException("User code not valid")

        response = json.loads(r.content)
        openid = response.get("openid")
        if not openid:
            raise APIAuthProviderException("Open ID not returned with successful auth.")

        registration_code = kwargs.get("registration_code")
        uid = self.validate_user(openid, registration_code=registration_code)
        self.set_refresh_token_if_exists(uid, response.get("refresh_token"))

        return {"access_token": response["access_token"], "uid": uid, "auth_type": self.auth_type, "expires": datetime.datetime.utcnow() + datetime.timedelta(seconds=response["expires_in"])}

    def refresh_token(self, token):
        payload = {"appid": self.config["client_id"], "refresh_token": token, "grant_type": "refresh_token"}
        r = requests.post(self.config["refresh_endpoint"], params=payload)
        if not r.ok:
            raise APIAuthProviderException("Unable to refresh token.")

        response = json.loads(r.content)
        return {"access_token": response["access_token"], "expires": datetime.datetime.utcnow() + datetime.timedelta(seconds=response["expires_in"])}

    def validate_user(self, openid, registration_code=None):
        if registration_code:
            user = config.db.users.find_one({"wechat.registration_code": registration_code})
            if user is None:
                raise APIUnknownUserException("Invalid or expired registration link.")

            # Check to make sure there is not already a user with this wechat openid:
            conflicts = config.db.users.find({"wechat.openid": openid})
            if conflicts.count() > 0:
                # For now, throw the error in access log so the site admin can find it
                log_map = {"access_type": "user_conflict", "timestamp": datetime.datetime.utcnow(), "conflicts": [c["_id"] for c in conflicts], "attempted_user": user["_id"]}
                config.log_db.access_log.insert_one(log_map)
                raise APIUnknownUserException("Another user is already registered with this Wechat OpenID.")
            update = {"$set": {"wechat.openid": openid}, "$unset": {"wechat.registration_code": ""}}
            config.db.users.update_one({"_id": user["_id"]}, update)
        else:
            user = config.db.users.find_one({"wechat.openid": openid})
        if not user:
            raise APIUnknownUserException("No user associated with this WeChat OpenID. Please use a valid registration link upon first sign in.")
        if user.get("disabled", False) is True:
            raise APIUnknownUserException("User {} is disabled.".format(user["_id"]))

        return user["_id"]

    # NOTE unused method
    def set_user_avatar(self, uid, identity):  # pragma: no cover
        pass


class CASAuthProvider(AuthProvider):
    def __init__(self):
        super(CASAuthProvider, self).__init__("cas")

    def validate_code(self, code, **kwargs):
        uid = self.validate_user(code)
        return {"access_token": code, "uid": uid, "auth_type": self.auth_type, "expires": datetime.datetime.utcnow() + datetime.timedelta(days=14)}

    def validate_user(self, token):
        service_url = config.get_item("site", "redirect_url") + self.config["service_url_state"]
        r = requests.get(self.config["verify_endpoint"], params={"ticket": token, "service": service_url})
        if not r.ok:
            raise APIAuthProviderException("User token not valid")

        username = self._parse_xml_response(r.content)
        uid = username + "@" + self.config["namespace"]

        self.ensure_user_exists(uid)
        self.set_user_gravatar(uid, uid)

        return uid

    def _parse_xml_response(self, response):

        # parse xml
        tree = ElementTree.fromstring(response)

        # check to see if xml response labeled request as success
        # see also: xml parsing in https://github.com/python-cas/python-cas
        if tree[0].tag.endswith("authenticationSuccess"):

            try:
                # get username from response
                namespace = tree.tag[0 : tree.tag.index("}") + 1]
                username = tree[0].find(".//" + namespace + "user").text
            except Exception as e:  # pylint: disable=broad-except
                config.log.warning(e)
                raise APIAuthProviderException("Unable to parse response from CAS provider.")

        else:
            raise APIAuthProviderException("Ticket verification unsuccessful.")

        return username


class SAMLAuthProvider(AuthProvider):
    def __init__(self):
        super(SAMLAuthProvider, self).__init__("saml")

    def validate_code(self, code, **kwargs):
        uid = self.validate_user(code)
        self.set_refresh_token_if_exists(uid, code)
        return {"access_token": code, "uid": uid, "auth_type": self.auth_type, "expires": datetime.datetime.utcnow() + datetime.timedelta(seconds=self.config["refresh_rate"]), "refresh_token": code}

    def validate_user(self, session_cookie):
        """
        Validate that a SAML cookie is associated with a session on the SP server.
        Retrieve user identifier.

        The verify endpoint will give information about the current session,
        including any attributes the IdP server chooses to share. All SP <-> IdP configurations
        should include the request for a unique user identifier, usually an email address.
        """
        r = requests.get(self.config["verify_endpoint"], cookies=session_cookie)
        if not r.ok:
            log_msg = "SAML request failed: {} - {}".format(r.status_code, r.reason)
            raise APIAuthProviderException("SAML session not valid", log_msg=log_msg)

        uid = None
        attributes = json.loads(r.content).get("attributes", [])

        for a in attributes:
            if a.get("name") == self.config["uid_key_name"]:
                values = a.get("values")
                uid = values[0] if values else None

        if not uid:
            raise APIAuthProviderException("Auth provider did not provide user email")

        self.ensure_user_exists(uid)
        self.set_user_gravatar(uid, uid)

        return uid

    def refresh_token(self, token):
        """
        Check to see if the session on the SP is still valid. Reject if not.
        """
        r = requests.get(self.config["verify_endpoint"], cookies=token)
        if not r.ok:
            raise APIAuthProviderException("SAML session no longer valid.")
        return {"access_token": token, "expires": datetime.datetime.utcnow() + datetime.timedelta(seconds=self.config["refresh_rate"])}


class APIKeyAuthProvider(AuthProvider):
    """
    Uses an API key for authentication.

    Note: This auth provider is mainly used for testing. A user
    can access the API directly by placing their API key in the
    Authorization header. There is no need for them to exchange
    the key for a session token in normal usecases.

    The static method is used by the base RequestHandler to
    verify the API key and attach it to a user.
    """

    def __init__(self):
        """
        Does not need to be supported in config.
        """
        super(APIKeyAuthProvider, self).__init__("api-key", set_config=False)

    def validate_code(self, code, **kwargs):

        api_key = APIKey.validate(code)
        if api_key["type"] != "user":
            raise APIAuthProviderException("Only user API keys can be used to grant a session.")
        return {"access_token": code, "uid": api_key["origin"]["id"], "auth_type": self.auth_type, "expires": datetime.datetime.utcnow() + datetime.timedelta(hours=1)}


AuthProviders = {"google": GoogleOAuthProvider, "ldap": JWTAuthProvider, "wechat": WechatOAuthProvider, "api-key": APIKeyAuthProvider, "cas": CASAuthProvider, "saml": SAMLAuthProvider}
