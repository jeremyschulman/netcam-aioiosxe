#  Copyright 2023 Jeremy Schulman
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

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

import httpx

# -----------------------------------------------------------------------------
# Private Imports
# -----------------------------------------------------------------------------

from netcam_aioiosxe.iosxe_plugin_globals import g_iosxe

# -----------------------------------------------------------------------------
# Exports
# -----------------------------------------------------------------------------

__all__ = ["IOSXERestConf"]


# -----------------------------------------------------------------------------
#
#                                 CODE BEGINS
#
# -----------------------------------------------------------------------------


class IOSXERestConf(httpx.AsyncClient):
    """
    IOS-XE RESTCONF asyncio client that uses JSON by default
    """

    def __init__(self, host: str):
        base_url = httpx.URL(f"https://{host}/restconf")

        super().__init__(
            base_url=base_url,
            auth=g_iosxe.basic_auth_read,
            verify=False,
            timeout=g_iosxe.config.timeout,
        )

        self.headers["accept"] = "application/yang-data+json"
        self.headers["content-type"] = "application/yang-data+json"
