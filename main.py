"""MIT License

Copyright (c) 2019-Current EvieePy

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import ipaddress
import os
import subprocess
import sys


HELLO = """
╔══════════════════════════════════════════════════════════╗
║ ░█░█░█▀▀░░░▀█▀░█░█░█▀█░█▀█░█▀▀░█░░░░░█▀▀░█▀▀░▀█▀░█░█░█▀█ ║
║ ░█▀█░█▀▀░░░░█░░█░█░█░█░█░█░█▀▀░█░░░░░▀▀█░█▀▀░░█░░█░█░█▀▀ ║
║ ░▀░▀░▀▀▀░░░░▀░░▀▀▀░▀░▀░▀░▀░▀▀▀░▀▀▀░░░▀▀▀░▀▀▀░░▀░░▀▀▀░▀░░ ║
╚══════════════════════════════════════════════════════════╝
"""

DETAILS_MESSAGE = """
================================================================================================================================================
To continue we need the HE Tunnel Details:
          
    Legend:
        (1) > HE Server IPv4 Address
            - The HE "Server IPv4 Address" found under the "IPv6 Tunnel Endpoints" section.
        (2) > HE Client IPv6 Address
            - The HE "Client IPv6 Address" found under the "IPv6 Tunnel Endpoints" section.
        (3) > Client Address
            - The IPv4 address of the machine you are running this script and which was provided to HE.
        (4) > Routed Address
            - The Routed IPv6 address of the HE Tunnel (Including the /48) found under the "Routed IPv6 Prefixes" section.
================================================================================================================================================
"""

NO_BIND = """
Unable to bind IPv6 automatically. Please run the following commands manually:
              
    sudo sysctl -w net.ipv6.ip_nonlocal_bind=1
    sudo echo 'net.ipv6.ip_nonlocal_bind = 1' >> /etc/sysctl.conf

After, validate the Tunnel with:

    ping6 -c 4 google.com


If you have issues make sure you have entered the correct details and try running this script again.
"""

SERVICE_FILE = """
Description=HurricaneElectric Tunnel
After=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart={0} tunnel add he-ipv6 mode sit remote {1} local {3} ttl 255
ExecStart={0} link set he-ipv6 up mtu 1480
ExecStart={0} addr add {2}/64 dev he-ipv6
ExecStart={0} -6 route add ::/0 dev he-ipv6
ExecStart={0} -6 route replace local {4}{5} dev he-ipv6
ExecStop={0} -6 route del ::/0 dev he-ipv6
ExecStop={0} link set he-ipv6 down
ExecStop={0} tunnel del he-ipv6

[Install]
WantedBy=multi-user.target
"""

print(HELLO, end="\n\n")


def check_sys():
    # Check for Linux based systems...
    # Use startswith instead of equality since Python <= 3.3 can return linux2 or linux
    if not sys.platform.startswith("linux"):
        raise EnvironmentError(
            "This script is only supported on Linux, and may not function on older versions."
        )


def prompt_sudo():
    # We need sudo access to issue some of these commands...
    # If we aren't already running as root access, ask the user for their sudoer password...
    if os.geteuid() == 0:
        return True

    message = "[sudo] password for %u:"
    ec = subprocess.check_call("sudo -v -p '%s'" % message, shell=True)

    return not bool(ec)


def validate_ips(data):
    # Do basic validation on the IP Addresses...
    # We don't actually know if any of these are correct until we start the service...

    try:
        ip_ = ipaddress.ip_address(data["endpoint"])
        if not isinstance(ip_, ipaddress.IPv4Address):
            raise ValueError
    except ValueError:
        raise RuntimeError(
            'The provided "HE Server IPv4 Address" is not a valid IPv4 address.'
        )

    heclient = data["client"]
    heclient = heclient.replace("/64", "")

    try:
        ip_ = ipaddress.ip_address(heclient)
        if not isinstance(ip_, ipaddress.IPv6Address):
            raise ValueError
    except ValueError:
        raise RuntimeError(
            'The provided "HE Client IPv6 Address" is not a valid IPv6 address.'
        )
    else:
        data["client"] = heclient

    try:
        ip_ = ipaddress.ip_address(data["local"])
        if not isinstance(ip_, ipaddress.IPv4Address):
            raise ValueError
    except ValueError:
        raise RuntimeError('The provided "Client Address" is not a valid IPv4 address.')

    routed = str(data["routed"])
    block = None

    if routed.endswith("/48"):
        block = "/48"
        routed = routed.replace("/48", "")
    elif routed.endswith("/64"):
        block = "/64"
        routed = routed.replace("/64", "")
    else:
        raise RuntimeError(
            'The provided "Routed Address" does not include a "/48" or "/64" on the end.'
        )

    try:
        ip_ = ipaddress.ip_address(routed)
        if not isinstance(ip_, ipaddress.IPv6Address):
            raise ValueError
    except ValueError:
        raise RuntimeError('The provided "Routed Address" is not a valid IPv6 address.')

    if len(data.values()) != len(set(data.values())):
        raise RuntimeError(
            "You have provided 2 or more of the same IP Address. All provided IP addresses should be unique."
        )

    data["routed"] = routed
    data["block"] = block
    return data


def grab_details():
    print(DETAILS_MESSAGE)

    endpoint = input('Please enter the "HE Server IPv4 Address" (1) :: ')
    heclient = input('Please enter the "HE Client IPv6 Address" (2) :: ')
    localaddr = input('Please enter the "Client Address" (3) :: ')
    routed = input('Please enter the "Routed Address" including the /48 (4) :: ')

    data = {
        "endpoint": endpoint,
        "client": heclient,
        "local": localaddr,
        "routed": routed,
    }

    new = validate_ips(data)
    return new


def bind():
    # Use subprocess call instead of run for Python version compat...
    ec1 = subprocess.call("sudo sysctl -w net.ipv6.ip_nonlocal_bind=1", shell=True)
    ec2 = subprocess.call("sudo echo 'net.ipv6.ip_nonlocal_bind = 1' >> /etc/sysctl.conf", shell=True)

    return (ec1, ec2)


def ip_command_location():
    # Use subprocess call instead of run for Python version compat...
    try:
        out = subprocess.check_output("sudo which ip", shell=True)
    except subprocess.CalledProcessError:
        raise RuntimeError('Unable to find the "ip" command location.')

    return out.decode().strip()


def generate_service_file(data):
    print("Generating Service File...")

    content = SERVICE_FILE.format(
        data["iploc"],
        data["endpoint"],
        data["client"],
        data["local"],
        data["routed"],
        data["block"],
    )

    with open("./he-tunnel.service", "w") as fp:
        fp.write(content)

    # Move our temp service file to the systemd folder...
    # Ensure we create a backup incase we need to revert at some point...
    # Python may not have permission at this point so traditional moving methods may not work...
    # But since we got sudo perms we can use the mv linux command...
    subprocess.check_call(
        "sudo mv -i -b ./he-tunnel.service /etc/systemd/system", shell=True
    )


def enable_service():
    print("Restarting the systemctl daemon...")
    subprocess.check_call("sudo systemctl daemon-reload", shell=True)
    print("Successfully restarted the systemctl daemon..", end="\n\n")

    print("Enabling and starting the HE Tunnel Service...")
    subprocess.check_call("sudo systemctl enable he-tunnel.service", shell=True)
    subprocess.check_call("sudo systemctl restart he-tunnel.service", shell=True)
    print("Successfully started the HE Tunnel Service...", end="\n\n")


def validate_tunnel(data):
    # Ping Google on the IPv6 Tunnel...
    random = data["routed"] + "420"

    print("Validating Tunnel Settings...", end="\n\n")
    ec1 = subprocess.call("ping6 -c 4 google.com", shell=True)
    ec2 = subprocess.call("ping6 -c 4 -I {} google.com".format(random), shell=True)

    if ec1 > 0 or ec2 > 0:
        print(
            "\n\nCould not validate the integrity of the IPv6 Tunnel. If you have issues, please try re-running this script and checking your details are correct.",
            file=sys.stderr,
        )
    else:
        print("\n\nSuccessfully setup the HE IPv6 Tunnel.")


def main():
    check_sys()

    if not prompt_sudo():
        raise PermissionError(
            "This script requires privilleged access. Try running with 'sudo'."
        )

    iploc = ip_command_location()
    details = grab_details()
    details["iploc"] = iploc

    generate_service_file(details)
    enable_service()

    bound = bind()
    if bound[0] > 0 or bound[1] > 0:
        print(NO_BIND, file=sys.stderr, end="\n\n")
    else:
        validate_tunnel(details)


main()
