import os
import logging
import datetime

logger = logging.getLogger("SYSTEM")

def _resolve_home_path(path):
    """Resolve a path given relative to the home directory.

    `os.path.join(home, "~/x")` yields a literal `~` directory, so expand first;
    an absolute path passes through unchanged.
    """
    return os.path.join(os.path.expanduser("~"), os.path.expanduser(path))

def ensure_dir_exists(path):
    """Create a directory and its parents. Accepts absolute or ~-relative paths."""
    target_path = os.path.expanduser(path)
    os.makedirs(target_path, exist_ok=True)
    logger.info(f"Directory ready: {target_path}")
    return target_path

def ensure_home_subdir_exists(subdir_name):
    ensure_dir_exists(_resolve_home_path(subdir_name))

def ensure_home_file_exists(filename, content=""):
    file_path = _resolve_home_path(filename)

    if not os.path.isfile(file_path):
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w') as f:
            f.write(content)
        logger.info(f"Created file: {file_path}")
    else:
        logger.info(f"File already exists: {file_path}")

def ensure_dev_certs(args):
    if not args.udp or args.certfile is not None:
        return args

    home_dir = os.path.expanduser("~")
    certs_dir = os.path.join(home_dir, "uav_api_certs")
    cert_path = os.path.join(certs_dir, "dev-cert.pem")
    key_path = os.path.join(certs_dir, "dev-key.pem")

    if not os.path.exists(certs_dir):
        os.makedirs(certs_dir)
        logger.info(f"Created directory: {certs_dir}")

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

        logger.info(f"Generated self-signed dev certs in: {certs_dir}")
    else:
        logger.info(f"Using existing dev certs from: {certs_dir}")

    args.certfile = cert_path
    args.keyfile = key_path
    return args

def setup(args):

    locations = "AbraDF=-15.840081,-47.926642,1042,30\nAbradf1=-15.8427104,-47.9231787,1042,30\nAbradf2=-15.8415750,-47.9290581,1042,30\nAbradf3=-15.8436186,-47.9262686,1042,30"

    ensure_home_subdir_exists(".config/ardupilot")
    ensure_home_file_exists(".config/ardupilot/locations.txt", locations)

    # Each of the three directories below is resolved and created unconditionally,
    # whether the path was defaulted here or supplied in a config file. The
    # `if ... is None` guards only choose the default; they must not also be the
    # only thing that creates the directory, because a deployment that configures
    # these paths explicitly then gets none of them.

    if args.log_path is None:
        args.log_path = _resolve_home_path(
            os.path.join("uav_api_logs", "uav_logs", f"uav_{args.sysid}.log")
        )

    args.log_path = os.path.expanduser(args.log_path)
    # log.resolve_log_file creates this too -- it has to, because logging is
    # configured before setup() runs -- but doing it here keeps setup() honest
    # about what it guarantees.
    ensure_dir_exists(os.path.dirname(os.path.abspath(args.log_path)))

    if args.simulated:
        # lifespan.py passes this to sim_vehicle.py as --use-dir regardless of
        # what log_path is set to, so it cannot hang off the branch above.
        ensure_home_subdir_exists("uav_api_logs/ardupilot_logs")

    if args.script_logs is None:
        args.script_logs = _resolve_home_path(os.path.join("uav_api_logs", "script_logs"))

    # A missing script_logs directory fails silently and expensively:
    # /mission/execute-script builds a shell redirection into it, so bash aborts
    # before running python while tmux still starts and the endpoint still
    # returns 200. The caller sees a script that ran and finished instantly.
    args.script_logs = ensure_dir_exists(args.script_logs)

    # scripts_path defaults to the literal string "~/uav_scripts" rather than
    # None, so the guard alone never created it and /mission/upload-script
    # returned 500.
    if args.scripts_path is None:
        args.scripts_path = _resolve_home_path("uav_scripts")

    args.scripts_path = ensure_dir_exists(args.scripts_path)

    args = ensure_dev_certs(args)

    return args