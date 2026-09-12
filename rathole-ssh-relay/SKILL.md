---
name: rathole-ssh-relay
description: Set up and maintain SSH access from a Mac to a private Ubuntu host through a public Ubuntu relay with rathole. Use when the user wants aliases like `ssh asus` for the private host and `ssh aliyun` for the public relay, without using WireGuard.
---

# Rathole SSH Relay

Use this skill when:
- A is the local Mac.
- B is a private Ubuntu host, such as an ASUS gaming machine or home server.
- C is a public Ubuntu server, such as an Alibaba Cloud ECS instance.
- B cannot reliably receive inbound public SSH, so B must dial out to C.
- A should connect with a normal SSH alias such as `ssh asus`.

This skill replaces the older WireGuard hub setup. For this workflow, A does not need `rathole`; only B and C run it.

Traffic flow:

```text
A(Mac) ssh -> C(public):2201 -> rathole server -> rathole client on B -> B:127.0.0.1:22
```

Typical aliases:
- `ssh asus`: connect to B through C's forwarded port.
- `ssh aliyun`: connect directly to C for relay administration.

Typical ports:
- `2333/tcp`: B's `rathole` client connects to C's `rathole` server.
- `2201/tcp`: A connects here to reach B's SSH service.
- `22/tcp`: A connects here to administer C itself.

## Assumptions

- C has a public IPv4 address.
- C security group allows `22/tcp`, `2333/tcp`, and `2201/tcp`.
- B can make outbound TCP connections to C.
- B has `openssh-server` listening on `127.0.0.1:22`.
- A has a working SSH key, usually `~/.ssh/id_ed25519`.
- Real tokens and private keys must stay out of git-tracked skill files.

## Quick Workflow

1. On C, install `rathole`, generate a shared token, and generate a Noise keypair.
2. On C, run `rathole` as a server on `0.0.0.0:2333`.
3. On C, expose service `asus_ssh` on `0.0.0.0:2201`.
4. On B, install `rathole` and run it as a client to `<C_PUBLIC_IP>:2333`.
5. On B, map service `asus_ssh` to `127.0.0.1:22`.
6. On A, configure SSH aliases for `asus` and `aliyun`.
7. Verify with `ssh asus hostname` and `ssh aliyun hostname`.

## C: Public Relay

Install `rathole`:

```bash
sudo apt update
sudo apt install -y curl unzip
cd /tmp
curl -L https://github.com/rathole-org/rathole/releases/download/v0.5.0/rathole-x86_64-unknown-linux-gnu.zip -o rathole.zip
unzip -o rathole.zip
sudo install -m 755 rathole /usr/local/bin/rathole
rathole --version
```

Generate credentials on C:

```bash
openssl rand -hex 16
rathole --genkey
```

Keep these values:
- `TOKEN`: shared by the C server service and B client service.
- `SERVER_PRIVATE_KEY`: used only on C.
- `SERVER_PUBLIC_KEY`: copied to B.

Write `/etc/rathole/server.toml` on C:

```toml
[server]
bind_addr = "0.0.0.0:2333"

[server.transport]
type = "noise"

[server.transport.noise]
local_private_key = "<SERVER_PRIVATE_KEY>"

[server.services.asus_ssh]
token = "<TOKEN>"
bind_addr = "0.0.0.0:2201"
```

Secure and inspect it:

```bash
sudo chmod 600 /etc/rathole/server.toml
sudo cat /etc/rathole/server.toml
```

Create `/etc/systemd/system/rathole-server.service` on C:

```ini
[Unit]
Description=Rathole Server
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/rathole -s /etc/rathole/server.toml
Restart=on-failure
RestartSec=5s
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
```

Start the server:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now rathole-server
sudo systemctl status rathole-server --no-pager
```

If C uses `ufw`:

```bash
sudo ufw allow 22/tcp
sudo ufw allow 2333/tcp
sudo ufw allow 2201/tcp
sudo ufw reload
```

Also open `22/tcp`, `2333/tcp`, and `2201/tcp` in the cloud security group. Prefer restricting `2201/tcp` to A's public IP when possible.

## B: Private Ubuntu Host

Make sure B can accept local SSH:

```bash
sudo apt update
sudo apt install -y openssh-server curl unzip
sudo systemctl enable --now ssh
sudo systemctl status ssh --no-pager
```

Install `rathole` on B:

```bash
cd /tmp
curl -L https://github.com/rathole-org/rathole/releases/download/v0.5.0/rathole-x86_64-unknown-linux-gnu.zip -o rathole.zip
unzip -o rathole.zip
sudo install -m 755 rathole /usr/local/bin/rathole
rathole --version
```

Write `/etc/rathole/client.toml` on B:

```toml
[client]
remote_addr = "<C_PUBLIC_IP>:2333"

[client.transport]
type = "noise"

[client.transport.noise]
remote_public_key = "<SERVER_PUBLIC_KEY>"

[client.services.asus_ssh]
token = "<TOKEN>"
local_addr = "127.0.0.1:22"
```

The service name must match C exactly. If C uses `[server.services.asus_ssh]`, B must use `[client.services.asus_ssh]`.

Secure and inspect it:

```bash
sudo chmod 600 /etc/rathole/client.toml
sudo cat /etc/rathole/client.toml
```

Create `/etc/systemd/system/rathole-client.service` on B:

```ini
[Unit]
Description=Rathole Client
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/rathole -c /etc/rathole/client.toml
Restart=on-failure
RestartSec=5s
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
```

Start the client:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now rathole-client
sudo systemctl status rathole-client --no-pager
```

Healthy client logs usually include:

```text
Control channel ... established
```

## A: Mac SSH Aliases

Configure A in `~/.ssh/config`. This is what makes `ssh asus` replace the full IP, port, and user command.

```sshconfig
Host asus
  HostName <C_PUBLIC_IP>
  Port 2201
  User three
  IdentityFile ~/.ssh/id_ed25519
  IdentitiesOnly yes
  AddKeysToAgent yes
  UseKeychain yes

Host aliyun
  HostName <C_PUBLIC_IP>
  Port 22
  User root
  IdentityFile ~/.ssh/id_ed25519
  IdentitiesOnly yes
  AddKeysToAgent yes
  UseKeychain yes
```

Then:

```bash
ssh asus
ssh aliyun
```

Equivalent expanded commands:

```bash
ssh -p 2201 three@<C_PUBLIC_IP>
ssh -p 22 root@<C_PUBLIC_IP>
```

The first command lands on B because C's `rathole` server forwards `2201` to B's `127.0.0.1:22`.

## Public Key Login

Use public key login instead of saving remote passwords.

To allow A's key to log into B through the relay:

```bash
ssh asus 'mkdir -p ~/.ssh && chmod 700 ~/.ssh'
cat ~/.ssh/id_ed25519.pub | ssh asus 'cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'
```

To allow A's key to log into C:

```bash
ssh aliyun 'mkdir -p ~/.ssh && chmod 700 ~/.ssh'
cat ~/.ssh/id_ed25519.pub | ssh aliyun 'cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'
```

On macOS, `UseKeychain yes` remembers the private key passphrase, not the remote account password.

## Add a Classmate's Mac

Use this when another Mac should SSH to B through the same existing `rathole` relay. The classmate does not need to install `rathole`; only their SSH public key and local SSH alias are needed.

Do not share A's private key. The classmate should generate and keep their own key on their own Mac:

```bash
ssh-keygen -t ed25519 -C "classmate@mac"
cat ~/.ssh/id_ed25519.pub
```

They send only the single public key line that starts with `ssh-ed25519`.

On A or any machine that can already `ssh asus`, append the classmate's public key to B's login user's `authorized_keys`:

```bash
ssh asus
mkdir -p ~/.ssh
chmod 700 ~/.ssh
printf '%s\n' '<CLASSMATE_PUBLIC_KEY_LINE>' >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

Then the classmate adds this to their own `~/.ssh/config`:

```sshconfig
Host asus
  HostName <C_PUBLIC_IP>
  Port 2201
  User three
  IdentityFile ~/.ssh/id_ed25519
  IdentitiesOnly yes
  AddKeysToAgent yes
  UseKeychain yes
```

They verify from their Mac:

```bash
ssh -G asus | sed -n '1,40p'
ssh asus hostname
```

If C's cloud security group restricts `2201/tcp` to A's public IP, add the classmate's current public IP to that rule too. Do not give the classmate `ssh aliyun` access unless they also need to administer C.

To revoke access later, remove that exact public key line from B's `~/.ssh/authorized_keys`.

## Verification

From A:

```bash
ssh -G asus | sed -n '1,40p'
ssh -G aliyun | sed -n '1,40p'
nc -vz <C_PUBLIC_IP> 2201
ssh -o BatchMode=yes -o ConnectTimeout=5 asus hostname
ssh -o BatchMode=yes -o ConnectTimeout=5 aliyun hostname
```

Expected:
- `asus` resolves to `<C_PUBLIC_IP>:2201` with user `three`.
- `aliyun` resolves to `<C_PUBLIC_IP>:22` with user `root`.
- `ssh asus hostname` returns B's hostname.
- `ssh aliyun hostname` returns C's hostname.

From C:

```bash
sudo systemctl status rathole-server --no-pager
sudo journalctl -u rathole-server -n 80 --no-pager
```

From B:

```bash
sudo systemctl status rathole-client --no-pager
sudo journalctl -u rathole-client -n 80 --no-pager
sudo systemctl status ssh --no-pager
```

## VS Code Remote SSH

After the SSH alias works in a normal terminal, VS Code Remote SSH should use the same alias:

```text
asus
```

First open can be slow because VS Code installs and starts its remote server under `~/.vscode-server/` on B. Later opens are faster because the server, extensions, and language-server caches are already present.

## Common Failure Modes

`ssh asus` times out:
- C security group or firewall is blocking `2201/tcp`.
- B's `rathole-client` is not connected.

`rathole-client` cannot connect to C:
- C security group or firewall is blocking `2333/tcp`.
- `remote_addr` is wrong.
- Token or Noise public key is wrong.

`Permission denied`:
- The SSH username is wrong.
- A's public key is not in B's or C's `authorized_keys`.
- SSH is configured to reject that login user.

`ssh asus` reaches the wrong host:
- C and B service names do not match.
- C's `2201` is mapped to a different service.

VS Code connects in terminal but fails in Remote SSH:
- Check that VS Code is using the same local `~/.ssh/config`.
- Use the alias `asus`, not the raw relay IP, if the port and user are only defined in the alias.
- Inspect B's `~/.vscode-server/` if the SSH connection succeeds but VS Code server startup fails.

## Security Notes

- Keep `TOKEN`, `SERVER_PRIVATE_KEY`, and live config files out of git.
- Prefer key login and disable password login only after key login is confirmed.
- Restrict `2201/tcp` to A's public IP if the IP is stable.
- Use `IdentitiesOnly yes` when a host should use exactly one key.
