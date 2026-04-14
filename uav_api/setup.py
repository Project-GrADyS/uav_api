import os
import datetime

def ensure_home_subdir_exists(subdir_name):
    home_dir = os.path.expanduser("~")  # Gets the home directory path
    target_path = os.path.join(home_dir, subdir_name)

    if not os.path.exists(target_path):
        os.makedirs(target_path)
        print(f"Created directory: {target_path}")
    else:
        print(f"Directory already exists: {target_path}")

def ensure_home_file_exists(filename, content=""):
    home_dir = os.path.expanduser("~")  # Gets the user's home directory
    file_path = os.path.join(home_dir, filename)

    if not os.path.isfile(file_path):
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"Created file: {file_path}")
    else:
        print(f"File already exists: {file_path}")

def ensure_dev_certs(args):
    if not args.udp or args.certfile is not None:
        return args

    home_dir = os.path.expanduser("~")
    certs_dir = os.path.join(home_dir, "uav_api_certs")
    cert_path = os.path.join(certs_dir, "dev-cert.pem")
    key_path = os.path.join(certs_dir, "dev-key.pem")

    if not os.path.exists(certs_dir):
        os.makedirs(certs_dir)
        print(f"Created directory: {certs_dir}")

    if not os.path.isfile(cert_path) or not os.path.isfile(key_path):
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import ipaddress

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "uav-api-dev"),
        ])

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
            .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365))
            .add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                    x509.IPAddress(ipaddress.IPv4Address("0.0.0.0")),
                ]),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )

        with open(key_path, "wb") as f:
            f.write(key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            ))

        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        print(f"Generated self-signed dev certs in: {certs_dir}")
    else:
        print(f"Using existing dev certs from: {certs_dir}")

    args.certfile = cert_path
    args.keyfile = key_path
    return args

def setup(args):

    locations = "AbraDF=-15.840081,-47.926642,1042,30\nAbradf1=-15.8427104,-47.9231787,1042,30\nAbradf2=-15.8415750,-47.9290581,1042,30\nAbradf3=-15.8436186,-47.9262686,1042,30"

    ensure_home_subdir_exists(".config/ardupilot")
    ensure_home_file_exists(".config/ardupilot/locations.txt", locations)

    if args.log_path is None:
        ensure_home_subdir_exists("uav_api_logs")
        ensure_home_subdir_exists("uav_api_logs/uav_logs")
        ensure_home_file_exists(f"uav_api_logs/uav_logs/uav_{args.sysid}.log")
        if args.simulated:
            ensure_home_subdir_exists("uav_api_logs/ardupilot_logs")

        home_dir = os.path.expanduser("~")  # Gets the user's home directory
        args.log_path = os.path.join(home_dir, "uav_api_logs","uav_logs",f"uav_{args.sysid}.log")

    if args.script_logs is None:
        ensure_home_subdir_exists("uav_api_logs")
        ensure_home_subdir_exists("uav_api_logs/script_logs")

        home_dir = os.path.expanduser("~")  # Gets the user's home directory
        args.script_logs = os.path.join(home_dir, "uav_api_logs","script_logs")

    if args.scripts_path is None:
        ensure_home_subdir_exists("uav_scripts")
        args.scripts_path = os.path.join(home_dir, "uav_scripts")

    args = ensure_dev_certs(args)

    return args