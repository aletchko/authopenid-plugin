# -*- coding: utf-8 -*-
from __future__ import absolute_import

from trac.core import Interface
from genshi.builder import tag
from genshi.core import escape

from openid.consumer.discover import DiscoveryFailure ; 'SIDE-EFFECTS'

from authopenid.util import MultiDict



FULL_NAME = 'openid.fullname'
EMAIL_ADDRESS = 'openid.email'
NICKNAME = 'openid.nickname'

class OpenIDException(Exception):
    def __html__(self):
        if len(self.args) > 0:
            message = self.args[0]
        else:
            message = self.__class__.__name__
        return escape(message)

    def __unicode__(self):
        return unicode(self.__html__().striptags().stripentities())

    def __str__(self):
        return self.__unicode__().encode('utf-8')

class NotAuthorized(OpenIDException):
    """ User is not allowed here

    This exception is raised by authorization policies to indicate that
    user (identified by a successful OpenID authentication request) should
    not be allowed to log in.

    """

class NegativeAssertion(OpenIDException):
    """ OpenID authentication returned a negative assertion

    Subclasses of :exc:`NegativeAssertion` are raised by
    :meth:`OpenIDConsumer.complete` to indicate that the user could
    not be successfull authenticated.

    """

class AuthenticationCancelled(NegativeAssertion):
    """ The user cancelled the authentication process.

    Raised by :meth:`OpenIDConsumer.complete` to indicate that the
    user cancelled the OpenID authentication process.

    """

class SetupNeeded(NegativeAssertion):
    """ Immediate authentication failed.

    Raised by :meth:`OpenIDConsumer.complete` in response to an
    'immediate' (non-interactive) authentication request to indicate
    that the user interaction (at the provider side) is required to
    complete authentication.

    """
    def __init__(self, setup_url=None):
        message = "Setup needed"
        if setup_url:
            message = tag.a(message, href=setup_url)
        super(SetupNeeded, self).__init__(message, setup_url)

    @property
    def setup_url(self):
        return self.args[1]

class AuthenticationFailed(NegativeAssertion):
    """ OpenId Authentication failed.

    Raised by :meth:`OpenIDConsumer.complete` to indicate
    a failure of OpenID authentication.   This error indicates an
    protocol error (invalid request or response format, etc.) of some
    sort.  (It *does not* mean 'password didn't match'.)

    """
    def __init__(self, reason=None, identity_url=None):
        msg = tag("Authentication failed")
        if identity_url:
            msg += tag(" for ", tag.code(identity_url))
        if reason:
            msg += tag(": ", reason)
        super(AuthenticationFailed, self).__init__(msg, reason, identity_url)

    @property
    def reason(self):
        return self.args[1]

    @property
    def identity_url(self):
        return self.args[2]

class OpenIDIdentifier(str):
    """ Represents an OpenID identifier response as received from an OP

    This class represents the results of a successful OpenID authentication.

    Additionally, the ``OpenIDIdentifier`` has a (multi-valued)
    dictionary containing additional data (e.g. full name and/or email
    address as determined via SREG or AX, for example.)  Certain keys
    in this dictionary have pre-defined meanings:

    :const:`FULL_NAME`
        The user's full name

    :const:`EMAIL_ADDRESS`,
        The user's email address

    :const:`NICKNAME`
        The user's 'nickname' (or 'username')

    Additional data may also be stored in the ``signed_data`` dictionary
    by extension providers.   (Such data should use keys which do not
    begin with ``'openid.'``.)

    """
    def __init__(self, identifier):
        self.signed_data = MultiDict()

    @property
    def identifier(self):
        return str(self)


class IOpenIDAuthnRequestListener(Interface):
    """ Components implementing :class:`IOpenIDAuthnRequestListener`
    can participate in the OpenID checkid requests.

    These components can, e.g., make requests for extra information
    from the OP via OpenID extension protocols.  They can also be used
    to prevent the use of certain OpenID providers (or particular)
    identifiers for authentication (though see also
    :class:`IOpenIDAuthorizationPolicy` for an interface with similar
    uses.)

    """

    def prepare_authn_request(req, auth_request):
        """ Possibly modify authn_request.

        This method is called before the authentication request is sent
        to the OP.  It might be used to add extension fields to the request.

        :type req: :class:`trac.web.api.Request`
        :type auth_request: :class:`openid.consumer.consumer.AuthRequest`

        """

    def parse_response(response, oid_identifier):
        """ Parse the response.

        This method is called after the receptions of an affirmative response
        to an authentication request.

        This method might be used to extract information from
        extension fields in the response.  In this case the method
        probably will want to add any extracted information to the
        ``signed_data`` multidict on the ``oid_identifier`` object.
        Generally any data should be appended to that already in the
        ``signed_data`` dict (using :meth:``MultiDict.add``).  That
        way data provider by earlier extension providers will take
        precedence over that provided by later ones.

        .. NOTE:: Only data which comes from signed response fields should be
            placed into the ``signed_data`` dict.

        This method can also be used to prevent the use of the
        identifier for authentication.  In this case the method should
        an exc:`AuthenticationFailed` exception to signal that the
        identifier should not be used for further authentication.

        :type response: :class:`openid.consumer.consumer.SuccessResponse`
        :type oid_identifier: :class:`OpenIDIdentifier`

        :raises: :exc:`AuthenticationFailed` if the data
            returned via the openid extension indicates that the
            entire OpenID response is not acceptable for use in
            authentication.  (This can be used, for example, to
            enforce the required use of certain PAPE authentication
            policies.)

        """

class IOpenIDAuthorizationPolicy(Interface):
    """ Provides support for authorizing OpenID users.

    An authorization policy checks the user's identity (as returned
    by a successful OpenID authentication request) to determine whether
    log-in should be allowed to proceed.

    """

    def authorize(req, identifier):
        """ Determine with user is authorized to log in.

        All of the configured authorization policies will be called to
        check whether the user is authorized to use this site.  If any
        of the policies raises :exc:`NotAuthorized`, or if no policy
        returns a true value, authorization will be denied; otherwise if
        any of the policies returns a true value, access will be granted.

        :type req: :class:`trac.web.api.Request`
        :type identifier: :class:`IOpenIDIdentifier`

        :returns: True if the user is authorized.  If the policy returns
            ``False``, it does not make any particular claims about the
            authorization of the user.

        :raises: :exc:`NotAuthorized` if the user is not authorized

        """

class IOpenIDUserDataProvider(Interface):
    """ Provides initial user data for new account registration via OpenID
    """
    def get_user_data(req, identifier):
        """ Get username and attributes for new account created via OpenID

        :type req: :class:`trac.web.api.Request`
        :type identifier: :class:`IOpenIDIdentifier`

        :returns: A pair ``(username, attributes)``, where ``attributes``
            is a dict of user attributes (probably containing keys ``'name'``
            and ``'email'`` as well as perhaps others.)
        """

# FIXME: Rename to UnknownUser ?
class UserNotFound(KeyError):
    pass

class OpenIDIdentifierInUse(OpenIDException, KeyError):
    def __init__(self, username, identifier):
        msg = escape("User %s is aready using identifier %s") % (
            tag.code(username), tag.code(identifier))
        super(OpenIDIdentifierInUse, self).__init__(msg, username, identifier)

    @property
    def username(self):
        return self.args[1]

    @property
    def identifier(self):
        return self.args[2]

class IOpenIDIdentifierStore(Interface):
    """ Manage the association between trac users and OpenID identifiers
    """
    def get_user(openid_identifier):
        """ Get trac username by OpenID identifier

        :returns: Trac username or ``None`` if no user found
        """

    def get_identifiers(username):
        """ Get OpenID identifiers for user
        """

    def add_identifier(username, openid_identifier):
        """ Add an OpenID identifier for the user

        :raises: :exc:`UserNotFound` if no user is found for ``username``
        :raises: :exc:`OpenIDIdentifierInUse` if another user is already
            associated with the ``openid_identifier``
        """

    def discard_identifier(username, openid_identifier):
        """ Remove an OpenID identifier for the user

        :raises: :exc:`UserNotFound` if no user is found for ``username``
        """

class IOpenIDUserRegistration(Interface):
    """ Creates new user accounts for OpenID authenticated users.

    Depending on configuration, this may or may not involve further
    user interaction.

    """
    def register_user(req, openid_identifier):
        """ Register a new OpenID-authenticated user.

        :raises: :exc:`RequestDone` This is a no-return method.
        """

class IOpenIDFancySelector(Interface):
    """ Support for pluggable fancy OpenID selectors.

    FIXME: Document
    """
    def populate_data(req, data):
        """ Mangle the template data
        """

class IOpenIDConsumer(Interface):
    """ Handle the nitty-gritty of OpenID authentication.

    Internal use.
    """
    def begin(req, identifier, return_to):
        """ Start the openid authentication process.

        If successful, a redirect is issued, either via HTTP redirect
        or via an auto-submitting HTML form response.  In either of these
        cases, this method is a 'no return' — it exists by raising
        a :exc:`trac.web.api.RequestDone` exception.

        :raises: :exc:`DiscoveryFailure`
        :raises: :exc:`trac.web.api.RequestDone`
            This is the _normal exit_ for the method.
        """

    def complete(req):
        """ Process authentication response.

        This handles the _indirect response_ to an OpenID authentication
        request.

        :rtype: :class:`OpenIDIndentifier`

        :raises: :exc:`AuthenticationCancelled`
        :raises: :exc:`SetupNeeded`
        :raises: :exc:`AuthenticationFailed`
        :raises: :exc:`ExtensionResponseUnacceptable`
        """

class IUserLogin(Interface):
    """ Handle setting/clearing of the auth cookie to actually log the user in

    Internal use.
    """
    def login(req, username, referer=None):
        """ Log the user in as ``username`` and redirect to ``referer``

        The current session must be anonymous.
        """

    def logout(req, referer=None):
        """ Log the user out and redirect to ``referer``
        """
