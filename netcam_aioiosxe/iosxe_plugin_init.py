#  Copyright 2021 Jeremy Schulman
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from pydantic import ValidationError

from .iosxe_plugin_config import IOSXEPluginConfig
from .iosxe_plugin_globals import g_iosxe


def iosxe_plugin_config(config: dict):
    """
    Called during plugin init, this function is used to setup the default
    credentials to access the EOS devices.

    Parameters
    ----------
    config: dict
        The dict object as defined in the User configuration file.
    """

    try:
        g_iosxe.config = IOSXEPluginConfig.parse_obj(config)
    except ValidationError as exc:
        raise RuntimeError(f"Failed to load IOS-XE plugin configuration: {str(exc)}")

    auth_read = g_iosxe.config.env.read

    g_iosxe.auth_read = (
        auth_read.username.get_secret_value(),
        auth_read.password.get_secret_value(),
    )

    # If the User provides the admin credential environment variobles, then set
    # up the admin authentication that is used for configruation management

    if admin := g_iosxe.config.env.admin:
        admin_user = admin.username.get_secret_value()
        admin_passwd = admin.password.get_secret_value()
        g_iosxe.auth_admin = (admin_user, admin_passwd)