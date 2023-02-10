from scrapli.driver.core.cisco_iosxe import AsyncIOSXEDriver

host = "bplabswstring01"

dev = AsyncIOSXEDriver(
    host=host,
    auth_username="neteng-chatops-read",
    auth_password="Nie.<RyEP$Gh%s",
    auth_strict_key=False,
    transport="asyncssh",
)
