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

# SITL home positions registered for every install. locations.txt is a
# location mandated by ArduPilot itself (~/.config/ardupilot), so it does NOT
# move under root_dir.
CUSTOM_LOCATIONS = {
    "AbraDF": "-15.840081,-47.926642,1042,30",
    "Abradf1": "-15.8427104,-47.9231787,1042,30",
    "Abradf2": "-15.8415750,-47.9290581,1042,30",
    "Abradf3": "-15.8436186,-47.9262686,1042,30",
}

def _parse_location_names(file_path):
    """Read the location names (the part before '=') from a locations.txt."""
    names = set()
    if os.path.isfile(file_path):
        with open(file_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    names.add(line.split("=", 1)[0].strip())
    return names

def merge_locations(file_path, wanted):
    """Append the missing entries of `wanted` (name -> 'lat,lon,alt,heading').

    Existing entries -- including a user's own -- are never touched. The old
    behavior wrote the file only when it did not exist, so on any machine with
    a pre-existing locations.txt (most ArduPilot dev machines) the custom
    locations were never added and SITL failed on the default --location with
    no hint why.
    """
    existing_content = ""
    if os.path.isfile(file_path):
        with open(file_path) as f:
            existing_content = f.read()
    existing_names = _parse_location_names(file_path)

    missing = [name for name in wanted if name not in existing_names]
    if not missing:
        return

    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "a") as f:
        # A hand-edited file may lack a trailing newline; without this the
        # first appended entry would glue onto the last existing line.
        if existing_content and not existing_content.endswith("\n"):
            f.write("\n")
        for name in missing:
            f.write(f"{name}={wanted[name]}\n")
    logger.info(f"Added SITL locations {missing} to {file_path}")

def validate_location(args, locations_file):
    """Fail fast on an unknown --location instead of letting SITL die opaquely.

    Known names come from the merged custom file, plus ArduPilot's built-in
    Tools/autotest/locations.txt when --ardupilot_path makes it findable. With
    sim_vehicle.py resolved from PATH the built-in list is not visible from
    here, so an unknown name only warns -- it may still be a built-in.
    """
    if args.location in _parse_location_names(locations_file):
        return

    if args.ardupilot_path is not None:
        builtin_file = os.path.join(
            os.path.expanduser(args.ardupilot_path), "Tools/autotest/locations.txt"
        )
        if os.path.isfile(builtin_file):
            if args.location in _parse_location_names(builtin_file):
                return
            raise SystemExit(
                f"Unknown SITL location '{args.location}': not in {locations_file} "
                f"nor in {builtin_file}. Register it in {locations_file} as "
                "NAME=lat,lon,alt,heading."
            )

    logger.warning(
        f"SITL location '{args.location}' not found in {locations_file}; "
        "if it is not an ArduPilot built-in either, sim_vehicle.py will fail to start."
    )

def resolve_root_dir(args):
    """Expand and absolutize args.root_dir, writing the result back.

    Everything derived from the root must use the resolved form: the value is
    serialized through UAV_ARGS into the ASGI worker, which may have a
    different working directory.
    """
    args.root_dir = os.path.abspath(os.path.expanduser(args.root_dir))
    return args.root_dir

def ardupilot_logs_dir(args):
    """SITL log directory under the root.

    lifespan.start_sitl passes this to sim_vehicle.py as --use-dir regardless
    of what log_path is set to, so it is derived from root_dir alone.
    """
    return os.path.join(resolve_root_dir(args), "logs", "ardupilot_logs")

def derive_paths(args):
    """Fill unset path arguments from root_dir; explicit values win.

    Kept separate from setup() so the derivation is testable without touching
    the user's home directory (setup() also writes ArduPilot's locations.txt).
    """
    root = resolve_root_dir(args)

    if args.log_path is None:
        args.log_path = os.path.join(root, "logs", "uav_logs", f"uav_{args.sysid}.log")
    args.log_path = os.path.expanduser(args.log_path)

    if args.script_logs is None:
        args.script_logs = os.path.join(root, "logs", "script_logs")

    if args.scripts_path is None:
        args.scripts_path = os.path.join(root, "scripts")

    return args

def ensure_dev_certs(args):
    if not args.udp or args.certfile is not None:
        return args

    certs_dir = os.path.join(resolve_root_dir(args), "certs")
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

    if args.simulated:
        locations_file = _resolve_home_path(".config/ardupilot/locations.txt")
        merge_locations(locations_file, CUSTOM_LOCATIONS)
        validate_location(args, locations_file)

    # Every directory below is resolved and created unconditionally, whether
    # the path was derived from root_dir or supplied explicitly. derive_paths
    # only chooses values; a deployment that configures these paths explicitly
    # must still get its directories created.
    args = derive_paths(args)

    # log.resolve_log_file creates this too -- it has to, because logging is
    # configured before setup() runs -- but doing it here keeps setup() honest
    # about what it guarantees.
    ensure_dir_exists(os.path.dirname(os.path.abspath(args.log_path)))

    if args.simulated:
        ensure_dir_exists(ardupilot_logs_dir(args))

    # A missing script_logs directory fails silently and expensively:
    # /mission/execute-script builds a shell redirection into it, so bash aborts
    # before running python while tmux still starts and the endpoint still
    # returns 200. The caller sees a script that ran and finished instantly.
    args.script_logs = ensure_dir_exists(args.script_logs)

    args.scripts_path = ensure_dir_exists(args.scripts_path)

    args = ensure_dev_certs(args)

    return args