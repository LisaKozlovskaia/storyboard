# Copyright (c) 2015 Hewlett-Packard Development Company, L.P.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import requests
from urlparse import parse_qs
from urlparse import urlparse
import uuid

from mock import patch
from oslo.config import cfg
import six

from storyboard.api.auth import ErrorMessages as e_msg
from storyboard.db.api import access_tokens as token_api
from storyboard.db.api import auth as auth_api
from storyboard.tests import base


CONF = cfg.CONF


class BaseOAuthTest(base.FunctionalTest):
    """Base functional test class, including reusable assertions."""

    def assertValidRedirect(self, response, redirect_uri,
                            expected_status_code, **kwargs):
        """Validate a redirected error response. All the URL components should
        match the original redirect_uri, with the exception of the parameters,
        which should contain an 'error' and an 'error_description' field of
        the provided types.

        :param redirect_uri: The expected redirect_uri
        :param response: The raw HTTP response.
        :param expected_status_code: The expected status code.
        :param kwargs: Parameters expected in the URI parameters.
        :return:
        """

        self.assertEqual(expected_status_code, response.status_code)
        # Split the url into parts.
        location = response.headers.get('Location')
        location_url = urlparse(location)
        parameters = parse_qs(location_url[4])

        # Break out the redirect uri to compare and make sure we're headed
        # back to the redirect URI with the appropriate error codes.
        configured_url = urlparse(redirect_uri)
        self.assertEqual(configured_url[0], location_url[0])
        self.assertEqual(configured_url[1], location_url[1])
        self.assertEqual(configured_url[2], location_url[2])
        self.assertEqual(configured_url[3], location_url[3])
        # 4 is ignored, it contains new parameters.
        self.assertEqual(configured_url[5], location_url[5])

        # Make sure we have the correct error response.
        self.assertEqual(len(kwargs), len(parameters))
        for key, value in six.iteritems(kwargs):
            self.assertIn(key, parameters)
            self.assertIsNotNone(parameters[key])
            self.assertEqual(value, parameters[key][0])


class TestOAuthAuthorize(BaseOAuthTest):
    """Functional tests for our /oauth/authorize endpoint. For more
    information, please see here: http://tools.ietf.org/html/rfc6749

    This is not yet a comprehensive test of this endpoint, though it hits
    the major error cases. Additional work as follows:

    * Test that including a request parameter more than once results in
    invalid_request
    * Test that server errors return with error_description="server_error"
    """

    valid_params = {
        'response_type': 'code',
        'client_id': 'storyboard.openstack.org',
        'redirect_uri': 'https://storyboard.openstack.org/#!/auth/token',
        'scope': 'user'
    }

    def test_valid_authorize_request(self):
        """This test ensures that the authorize request against the oauth
        endpoint succeeds with expected values.
        """

        random_state = six.text_type(uuid.uuid4())

        # Simple GET with various parameters
        response = self.get_json(path='/openid/authorize',
                                 expect_errors=True,
                                 state=random_state,
                                 **self.valid_params)

        # Assert that this is a redirect response
        self.assertEqual(303, response.status_code)

        # Assert that the redirect request goes to launchpad.
        location = response.headers.get('Location')
        location_url = urlparse(location)
        parameters = parse_qs(location_url[4])

        # Check the URL
        conf_openid_url = CONF.oauth.openid_url
        self.assertEqual(conf_openid_url, location[0:len(conf_openid_url)])

        # Check OAuth Registration parameters
        self.assertIn('fullname', parameters['openid.sreg.required'][0])
        self.assertIn('email', parameters['openid.sreg.required'][0])
        self.assertIn('nickname', parameters['openid.sreg.required'][0])

        # Check redirect URL
        redirect = parameters['openid.return_to'][0]
        redirect_url = urlparse(redirect)
        redirect_params = parse_qs(redirect_url[4])

        self.assertIn('/openid/authorize_return', redirect)
        self.assertEqual(random_state,
                         redirect_params['state'][0])
        self.assertEqual(self.valid_params['redirect_uri'],
                         redirect_params['sb_redirect_uri'][0])

    def test_authorize_invalid_response_type(self):
        """Assert that an invalid response_type redirects back to the
        redirect_uri and provides the expected error response.
        """
        invalid_params = self.valid_params.copy()
        invalid_params['response_type'] = 'invalid_code'

        # Simple GET with invalid code parameters
        random_state = six.text_type(uuid.uuid4())
        response = self.get_json(path='/openid/authorize',
                                 expect_errors=True,
                                 state=random_state,
                                 **invalid_params)

        # Validate the error response
        self.assertValidRedirect(response=response,
                                 expected_status_code=302,
                                 redirect_uri=invalid_params['redirect_uri'],
                                 error='unsupported_response_type',
                                 error_description=e_msg.INVALID_RESPONSE_TYPE)

    def test_authorize_no_response_type(self):
        """Assert that an nonexistent response_type redirects back to the
        redirect_uri and provides the expected error response.
        """
        invalid_params = self.valid_params.copy()
        del invalid_params['response_type']

        # Simple GET with invalid code parameters
        random_state = six.text_type(uuid.uuid4())
        response = self.get_json(path='/openid/authorize',
                                 expect_errors=True,
                                 state=random_state,
                                 **invalid_params)

        # Validate the error response
        self.assertValidRedirect(response=response,
                                 expected_status_code=302,
                                 redirect_uri=invalid_params['redirect_uri'],
                                 error='unsupported_response_type',
                                 error_description=e_msg.NO_RESPONSE_TYPE)

    def test_authorize_no_client(self):
        """Assert that a nonexistent client redirects back to the
        redirect_uri and provides the expected error response.
        """
        invalid_params = self.valid_params.copy()
        del invalid_params['client_id']

        # Simple GET with invalid code parameters
        random_state = six.text_type(uuid.uuid4())
        response = self.get_json(path='/openid/authorize',
                                 expect_errors=True,
                                 state=random_state,
                                 **invalid_params)

        # Validate the error response
        self.assertValidRedirect(response=response,
                                 expected_status_code=302,
                                 redirect_uri=invalid_params['redirect_uri'],
                                 error='invalid_client',
                                 error_description=e_msg.NO_CLIENT_ID)

    def test_authorize_invalid_scope(self):
        """Assert that an invalid scope redirects back to the
        redirect_uri and provides the expected error response.
        """
        invalid_params = self.valid_params.copy()
        invalid_params['scope'] = 'invalid_scope'

        # Simple GET with invalid code parameters
        random_state = six.text_type(uuid.uuid4())
        response = self.get_json(path='/openid/authorize',
                                 expect_errors=True,
                                 state=random_state,
                                 **invalid_params)

        # Validate the error response
        self.assertValidRedirect(response=response,
                                 expected_status_code=302,
                                 redirect_uri=invalid_params['redirect_uri'],
                                 error='invalid_scope',
                                 error_description=e_msg.INVALID_SCOPE)

    def test_authorize_no_scope(self):
        """Assert that a nonexistent scope redirects back to the
        redirect_uri and provides the expected error response.
        """
        invalid_params = self.valid_params.copy()
        del invalid_params['scope']

        # Simple GET with invalid code parameters
        random_state = six.text_type(uuid.uuid4())
        response = self.get_json(path='/openid/authorize',
                                 expect_errors=True,
                                 state=random_state,
                                 **invalid_params)

        # Validate the error response
        self.assertValidRedirect(response=response,
                                 expected_status_code=302,
                                 redirect_uri=invalid_params['redirect_uri'],
                                 error='invalid_scope',
                                 error_description=e_msg.NO_SCOPE)

    def test_authorize_invalid_redirect_uri(self):
        """Assert that an invalid redirect_uri returns a 400 message with the
        appropriate error message encoded in the body of the response.
        """
        invalid_params = self.valid_params.copy()
        invalid_params['redirect_uri'] = 'not_a_valid_uri'

        # Simple GET with invalid code parameters
        random_state = six.text_type(uuid.uuid4())
        response = self.get_json(path='/openid/authorize',
                                 expect_errors=True,
                                 state=random_state,
                                 **invalid_params)

        # Assert that this is NOT a redirect
        self.assertEqual(400, response.status_code)
        self.assertIsNotNone(response.json)
        self.assertEqual('invalid_request', response.json['error'])
        self.assertEqual(e_msg.INVALID_REDIRECT_URI,
                         response.json['error_description'])

    def test_authorize_no_redirect_uri(self):
        """Assert that a nonexistent redirect_uri returns a 400 message with
        the appropriate error message encoded in the body of the response.
        """
        invalid_params = self.valid_params.copy()
        del invalid_params['redirect_uri']

        # Simple GET with invalid code parameters
        random_state = six.text_type(uuid.uuid4())
        response = self.get_json(path='/openid/authorize',
                                 expect_errors=True,
                                 state=random_state,
                                 **invalid_params)

        # Assert that this is NOT a redirect
        self.assertEqual(400, response.status_code)
        self.assertIsNotNone(response.json)
        self.assertEqual('invalid_request', response.json['error'])
        self.assertEqual(e_msg.NO_REDIRECT_URI,
                         response.json['error_description'])


@patch.object(requests, 'post')
class TestOAuthAuthorizeReturn(BaseOAuthTest):
    """Functional tests for our /oauth/authorize_return, which handles
    responses from the launchpad service. The expected behavior here is that
    a successful response will 303 back to the client in accordance with
    the OAuth Authorization Response as described here:
    http://tools.ietf.org/html/rfc6749#section-4.1.2

    Errors from launchpad should be recast into the appropriate error code
    and follow the error responses in the same section.
    """
    valid_params = {
        'response_type': 'code',
        'client_id': 'storyboard.openstack.org',
        'sb_redirect_uri': 'https://storyboard.openstack.org/!#/auth/token',
        'scope': 'user',
        'openid.assoc_handle': '{HMAC-SHA1}{54d11f3f}{lmmpZg==}',
        'openid.ax.count.Email': 0,
        'openid.ax.type.Email': 'http://schema.openid.net/contact/email',
        'openid.ax.count.FirstName': 0,
        'openid.ax.type.FirstName': 'http://schema.openid.net/namePerson'
                                    '/first',
        'openid.ax.count.LastName': 0,
        'openid.ax.type.LastName': 'http://schema.openid.net/namePerson'
                                   '/last',
        'openid.ax.mode': 'fetch_response',

        # These two would usually be the OpenID URI.
        'openid.claimed_id': 'regularuser_openid',
        'openid.identity': 'regularuser_openid',

        'openid.mode': 'id_res',
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.ns.ax": "http://openid.net/srv/ax/1.0",
        "openid.ns.sreg": "http://openid.net/sreg/1.0",
        "openid.op_endpoint": "https://login.launchpad.net/+openid",
        "openid.response_nonce": "2015-02-03T19:19:27ZY5SIfO",
        "openid.return_to": "https://storyboard.openstack.org/api/v1/openid"
                            "/authorize_return?scope=user",
        "openid.sig=2ghVIBuCYDFe32cMOvY9rTCsQfg": "",
        "openid.signed": "assoc_handle,ax.count.Email,ax.count.FirstName,"
                         "ax.count.LastName,ax.mode,ax.type.Email,"
                         "ax.type.FirstName,ax.type.LastName,claimed_id,"
                         "identity,mode,ns,ns.ax,ns.sreg,op_endpoint,"
                         "response_nonce,return_to,signed,sreg.email,"
                         "sreg.fullname,sreg.nickname",
        "openid.sreg.email": "test@example.com",
        "openid.sreg.fullname": "Test User",
        "openid.sreg.nickname": "superuser"
    }

    def _mock_response(self, mock_post, valid=True):
        """Set the mock response from the openid endpoint to either true or
        false.

        :param mock_post: The mock to decorate.
        :param valid: Whether to provide a valid or invalid response.
        :return:
        """

        mock_post.return_value.status_code = 200
        if valid:
            mock_post.return_value.content = \
                'is_valid:true\nns:http://specs.openid.net/auth/2.0\n'
        else:
            mock_post.return_value.content = \
                'is_valid:false\nns:http://specs.openid.net/auth/2.0\n'

    def test_valid_response_request(self, mock_post):
        """This test ensures that the authorize request against the oauth
        endpoint succeeds with expected values.
        """
        self._mock_response(mock_post, valid=True)

        random_state = six.text_type(uuid.uuid4())

        # Simple GET with various parameters
        response = self.get_json(path='/openid/authorize_return',
                                 expect_errors=True,
                                 state=random_state,
                                 **self.valid_params)

        # Try to pull the code out of the response
        location = response.headers.get('Location')
        location_url = urlparse(location)
        parameters = parse_qs(location_url[4])
        token = auth_api.authorization_code_get(parameters['code'])

        # Validate the redirect response
        self.assertValidRedirect(response=response,
                                 expected_status_code=302,
                                 redirect_uri=
                                 self.valid_params['sb_redirect_uri'],
                                 state=token.state,
                                 code=token.code)

    def test_invalid_response_request(self, mock_post):
        """This test ensures that a failed authorize request against the oauth
        endpoint succeeds with expected values.
        """
        self._mock_response(mock_post, valid=False)

        random_state = six.text_type(uuid.uuid4())

        # Simple GET with various parameters
        response = self.get_json(path='/openid/authorize_return',
                                 expect_errors=True,
                                 state=random_state,
                                 **self.valid_params)

        # Validate the redirect response
        self.assertValidRedirect(response=response,
                                 expected_status_code=302,
                                 redirect_uri=
                                 self.valid_params['sb_redirect_uri'],
                                 error='access_denied',
                                 error_description=e_msg.OPEN_ID_TOKEN_INVALID)

    def test_invalid_redirect_no_name(self, mock_post):
        """If the oauth response to storyboard is valid, but does not include a
        first name, it should error.
        """
        self._mock_response(mock_post, valid=True)

        random_state = six.text_type(uuid.uuid4())

        invalid_params = self.valid_params.copy()
        del invalid_params['openid.sreg.fullname']

        # Simple GET with various parameters
        response = self.get_json(path='/openid/authorize_return',
                                 expect_errors=True,
                                 state=random_state,
                                 **invalid_params)

        # Validate the redirect response
        self.assertValidRedirect(response=response,
                                 expected_status_code=302,
                                 redirect_uri=
                                 self.valid_params['sb_redirect_uri'],
                                 error='invalid_request',
                                 error_description=e_msg.INVALID_NO_NAME)

    def test_invalid_redirect_no_email(self, mock_post):
        """If the oauth response to storyboard is valid, but does not include a
        first name, it should error.
        """
        self._mock_response(mock_post, valid=True)

        random_state = six.text_type(uuid.uuid4())

        invalid_params = self.valid_params.copy()
        del invalid_params['openid.sreg.email']

        # Simple GET with various parameters
        response = self.get_json(path='/openid/authorize_return',
                                 expect_errors=True,
                                 state=random_state,
                                 **invalid_params)

        # Validate the redirect response
        self.assertValidRedirect(response=response,
                                 expected_status_code=302,
                                 redirect_uri=
                                 self.valid_params['sb_redirect_uri'],
                                 error='invalid_request',
                                 error_description=e_msg.INVALID_NO_EMAIL)

    def test_invalid_redirect_no_username(self, mock_post):
        """If the oauth response to storyboard is valid, but does not include a
        first name, it should error.

        TODO: Remove during work for
        https://storyboard.openstack.org/#!/story/2000152
        """
        self._mock_response(mock_post, valid=True)

        random_state = six.text_type(uuid.uuid4())

        invalid_params = self.valid_params.copy()
        del invalid_params['openid.sreg.nickname']

        # Simple GET with various parameters
        response = self.get_json(path='/openid/authorize_return',
                                 expect_errors=True,
                                 state=random_state,
                                 **invalid_params)

        # Validate the redirect response
        self.assertValidRedirect(response=response,
                                 expected_status_code=302,
                                 redirect_uri=
                                 self.valid_params['sb_redirect_uri'],
                                 error='invalid_request',
                                 error_description=e_msg.INVALID_NO_NICKNAME)


class TestOAuthAccessToken(BaseOAuthTest):
    """Functional test for the /oauth/token endpoint for the generation of
    access tokens.
    """

    def test_valid_access_request(self):
        """This test ensures that the access token request may execute
        properly with a valid token.
        """

        # Generate a valid auth token
        authorization_code = auth_api.authorization_code_save({
            'user_id': 2,
            'state': 'test_state',
            'code': 'test_valid_code'
        })

        # POST with content: application/x-www-form-urlencoded
        response = self.app.post('/v1/openid/token',
                                 params={
                                     'code': authorization_code.code,
                                     'grant_type': 'authorization_code'
                                 },
                                 content_type=
                                 'application/x-www-form-urlencoded',
                                 expect_errors=True)

        # Assert that this is a successful response
        self.assertEqual(200, response.status_code)

        # Assert that the token came back in the response
        token = response.json
        self.assertIsNotNone(token['access_token'])
        self.assertIsNotNone(token['expires_in'])
        self.assertIsNotNone(token['id_token'])
        self.assertIsNotNone(token['refresh_token'])
        self.assertIsNotNone(token['token_type'])
        self.assertEqual('Bearer', token['token_type'])

        # Assert that the access token is in the database
        access_token = \
            token_api.access_token_get_by_token(token['access_token'])
        self.assertIsNotNone(access_token)

        # Assert that system configured values is owned by the correct user.
        self.assertEquals(2, access_token.user_id)
        self.assertEquals(token['id_token'], access_token.user_id)
        self.assertEqual(token['expires_in'], CONF.oauth.access_token_ttl)
        self.assertEqual(token['expires_in'], access_token.expires_in)
        self.assertEqual(token['access_token'], access_token.access_token)

        # Assert that the refresh token is in the database
        refresh_token = \
            auth_api.refresh_token_get(token['refresh_token'])
        self.assertIsNotNone(refresh_token)

        # Assert that system configured values is owned by the correct user.
        self.assertEquals(2, refresh_token.user_id)
        self.assertEqual(CONF.oauth.refresh_token_ttl,
                         refresh_token.expires_in)
        self.assertEqual(token['refresh_token'], refresh_token.refresh_token)

        # Assert that the authorization code is no longer in the database.
        self.assertIsNone(auth_api.authorization_code_get(
            authorization_code.code
        ))

    def test_invalid_grant_type(self):
        """This test ensures that invalid grant_type parameters get the
        appropriate error response.
        """

        # Generate a valid auth token
        authorization_code = auth_api.authorization_code_save({
            'user_id': 2,
            'state': 'test_state',
            'code': 'test_valid_code'
        })

        # POST with content: application/x-www-form-urlencoded
        response = self.app.post('/v1/openid/token',
                                 params={
                                     'code': authorization_code.code,
                                     'grant_type': 'invalid_grant_type'
                                 },
                                 content_type=
                                 'application/x-www-form-urlencoded',
                                 expect_errors=True)

        # Assert that this is a successful response
        self.assertEqual(400, response.status_code)
        self.assertIsNotNone(response.json)
        self.assertEqual('unsupported_grant_type', response.json['error'])
        self.assertEqual(e_msg.INVALID_TOKEN_GRANT_TYPE,
                         response.json['error_description'])
