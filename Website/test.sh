# Clean up any existing MongoDB repos to avoid conflicts
echo "=== Cleaning up existing MongoDB repositories ==="
sudo rm -f /etc/apt/sources.list.d/mongodb*.list
sudo apt-key del 7F0CEB10 2930ADAE8CAF5059EE73BB4B58712A2291FA4AD5 20691EEC35216C63CAF66CE1656408E390CFB1F5 4B7C549A058F8B6B 2069827F925C2E182330D4D4B5BEA7232F5C6971 E162F504A20CDF15827F718D4B7C549A058F8B6B 9DA31620334BD75D9DCB49F368818C72E52529D4 F5679A222C647C87527C2F8CB00A0BD1E2C63C11 2023-02-15 > /dev/null 2>&1 || true
# Update system packages
echo "=== Updating system packages ==="
sudo apt update || { echo "Failed to update package lists"; exit 1; }
# Add MongoDB repository depending on OS (Ubuntu Server or Linux Mint)
echo "=== Adding MongoDB repository ==="
# Detect OS id from /etc/os-release
OS_ID=$(awk -F= '/^ID=/{print $2}' /etc/os-release | tr -d '"')
# Prefer Ubuntu base codename from /etc/os-release when available
UBUNTU_BASE_CODENAME=$(awk -F= '/^UBUNTU_CODENAME=/{print $2}' /etc/os-release | tr -d '"')
if [ -z "$UBUNTU_BASE_CODENAME" ]; then
    UBUNTU_BASE_CODENAME=$(lsb_release -cs 2>/dev/null || awk -F= '/^VERSION_CODENAME=/{print $2}' /etc/os-release | tr -d '"')
fi
if [ "$OS_ID" = "linuxmint" ]; then
    # Map Linux Mint codename to Ubuntu base codename when needed
    MINT_CODENAME=$(lsb_release -cs 2>/dev/null || awk -F= '/^VERSION_CODENAME=/{print $2}' /etc/os-release | tr -d '"')
    if [ -z "$UBUNTU_BASE_CODENAME" ] || [ "$UBUNTU_BASE_CODENAME" = "$MINT_CODENAME" ]; then
        case "$MINT_CODENAME" in
            xia) UBUNTU_BASE_CODENAME="noble" ;;
            vanessa|vera|victoria) UBUNTU_BASE_CODENAME="jammy" ;;
            ulyana|ulyssa|uma|una) UBUNTU_BASE_CODENAME="focal" ;;
        esac
    fi
    echo "Detected Linux Mint ($MINT_CODENAME) → using Ubuntu base '$UBUNTU_BASE_CODENAME'"
elif [ "$OS_ID" = "ubuntu" ];
then
    echo "Detected Ubuntu ($UBUNTU_BASE_CODENAME)"
else
    echo "Non-Ubuntu/Mint OS detected ($OS_ID). Skipping MongoDB apt setup."
    exit 1
fi
# Select MongoDB series per Ubuntu base codename
case "$UBUNTU_BASE_CODENAME" in
    noble|jammy)
        MONGO_SERIES="7.0" ;;
    focal)
        MONGO_SERIES="6.0" ;;
    *)
        echo "Unknown Ubuntu codename '$UBUNTU_BASE_CODENAME', defaulting to 7.0"
        MONGO_SERIES="7.0" ;;
esac
# Use jammy repo path for noble until MongoDB publishes noble (avoid 404)
MONGO_APT_CODENAME="$UBUNTU_BASE_CODENAME"
if [ "$UBUNTU_BASE_CODENAME" = "noble" ]; then
    MONGO_APT_CODENAME="jammy"
    echo "Using jammy repo path for MongoDB on noble"
fi
# Install repo key and list using series and apt codename
wget -qO - https://www.mongodb.org/static/pgp/server-${MONGO_SERIES}.asc | sudo gpg --dearmor -o /usr/share/keyrings/mongodb-server-${MONGO_SERIES}.gpg
echo "deb [signed-by=/usr/share/keyrings/mongodb-server-${MONGO_SERIES}.gpg arch=amd64,arm64] https://repo.mongodb.org/apt/ubuntu ${MONGO_APT_CODENAME}/mongodb-org/${MONGO_SERIES} multiverse" | \
    sudo tee /etc/apt/sources.list.d/mongodb-org-${MONGO_SERIES}.list
# Install MongoDB
sudo apt-get update || exit 1
sudo apt-get install -y mongodb-org || exit 1