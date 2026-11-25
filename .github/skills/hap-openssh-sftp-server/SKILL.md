---
name: hap-openssh-sftp-server
description: Use the built-in macOS OpenSSH service for secure SFTP file transfers.
---

# **1. Skill Instructions**

## **1.1 Purpose**

Set up and verify macOS's built-in OpenSSH SFTP service. Do not install a
Python or third-party SFTP server.

## **1.2 Pause rule**

Run one step at a time. At each **PAUSE**, tell the user exactly what to do,
ask them to confirm with `ask_user`, and wait. Do not continue or claim a step
succeeded until it is verified. Before changing an OS setting or creating
persistent key access, get explicit approval. Never ask for a password or
private key.

## **1.3 Setup**

1. **Confirm the scope** — Ask which macOS account, which directory the user
   wants to test, which client device they will connect from, whether they
   already have a client key, and whether access should be LAN/VPN only or
   public. Default to LAN/VPN; do not infer permission to expose SSH publicly.

   **PAUSE:** Wait for the user's choices before proceeding.

2. **Check the current state** — On the Mac, run these read-only checks:

   ```sh
   id -un
   launchctl print system/com.openssh.sshd
   nc -z -G 3 127.0.0.1 22
   ```

   Then ask the user to open System Settings > General > Sharing > Remote
   Login and report whether it is on and which accounts are listed. Do not use
   `sudo` or request an administrator password.

   **PAUSE:** Wait for the Remote Login status and allowed account list.

3. **Enable restricted Remote Login** — If the current setting is already
   correct, leave it unchanged and skip this step's pauses. Otherwise propose
   enabling **Remote Login** for **Only these users**, with only the intended
   account selected. Keep **Allow full disk access for remote users** off.
   Remote Login also permits SSH shell access; it is not SFTP-only. Normal
   macOS account permissions apply. Do not promise a directory jail or
   isolation unless separately configured and verified.
   As of 2026-11-24, the user reported Remote Login enabled for only
   `bennyskov` and full disk access off; recheck these settings before use.

   **PAUSE A:** Explain the proposed setting and ask for approval. Wait.
   After approval, direct the user to open System Settings > General >
   Sharing > Remote Login and make the change.

   **PAUSE B:** Wait for the user to confirm the setting and allowed account.

   Apple instructions: [Allow a remote computer to access your Mac](https://support.apple.com/en-gw/guide/mac-help/mchlp1066/mac).

4. **Add a client public key** — Prefer a passphrase-protected Ed25519 key.
   Reuse a suitable existing key. Never overwrite either key file.

   For a new Windows key, check that neither target file exists, then use
   PowerShell:

   ```powershell
   New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.ssh" | Out-Null
   ssh-keygen -t ed25519 -a 64 -f "$env:USERPROFILE\.ssh\id_ed25519_sftp"
   Get-Content "$env:USERPROFILE\.ssh\id_ed25519_sftp.pub"
   ```

   For a new macOS key, use Terminal:

   ```sh
   mkdir -p -m 700 ~/.ssh
   ssh-keygen -t ed25519 -a 64 -f ~/.ssh/id_ed25519_sftp
   cat ~/.ssh/id_ed25519_sftp.pub
   ```

   Enter the passphrase locally. Transfer only the `.pub` line to the Mac
   through a trusted channel; never send a private key or paste keys into chat.

   **PAUSE A:** Confirm the intended Mac account by running `whoami` in that
   account's Terminal. Do not add a key if the account differs.

   **PAUSE B:** State the account and ask for approval before granting it key
   access. After approval, on the Mac run:

   ```sh
   install -d -m 700 ~/.ssh
   chmod 700 ~/.ssh
   touch ~/.ssh/authorized_keys
   chmod 600 ~/.ssh/authorized_keys
   nano -w ~/.ssh/authorized_keys
   ```

   In nano, keep all existing valid key lines. If the file already has
   content, press Down Arrow, then `Ctrl-E` to reach the end of the last line;
   press Return and paste only the new public-key line. If empty, paste the
   key directly. Save with `Ctrl-O`, press Return, and exit with `Ctrl-X`.
   Do not use `cat >>` for interactive key entry.

   If mistaken shell commands were pasted into the file, remove only lines
   that are clearly accidental. Preserve every valid key; if unsure, stop.

   **PAUSE C:** Wait for the user to confirm the file was saved.

5. **Test SFTP on the LAN** — Complete the hosts-file setup in **1.4** first
   if using the requested aliases. On the Mac, display the server fingerprint:

   ```sh
   ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
   ```

   From the client, start the connection below. At a first-connection host
   key prompt, stop and compare its fingerprint through a trusted channel.
   Accept the key only if the fingerprint matches:

   ```sh
   sftp -i /path/to-matching-private-key username@LAN-IP
   ```

   Replace the key-path and address placeholders. At the `sftp>` prompt,
   quote a remote path containing spaces:

   ```text
   cd "/remote/path/with spaces"
   pwd
   ls
   ```

   Verify the account and directory access match the request. Stop and report
   connection or permission errors; do not claim a transfer test unless one
   was performed.

   If the LAN test passes, report **LAN SFTP ready** only. Do not imply public
   access or a file transfer was verified.

   **PAUSE:** Have the user confirm the fingerprint and test result. Ask
   before creating or deleting any test file.

6. **Verify existing public forwarding** — The user confirmed on 2026-11-24
   that the BE3600 Dual-Band Wi-Fi 7 router already has this rule:

   | Setting                  | Configured value |
   | ------------------------ | ---------------- |
   | Service Name             | `sftp-bens`      |
   | Device IP Address        | `192.168.1.222`  |
   | External individual Port | `22`             |
   | Internal Port            | `22`             |
   | Protocol                 | `TCP`            |

   The supplied public IP is `84.246.243.130`. This is a user-reported
   configuration, not a verified external connection. Do not recreate the rule.

   - Verify the Mac still uses `192.168.1.222` and the WAN IP is still current.
   - Keep the LAN address stable with a DHCP reservation or equivalent.
   - Confirm restricted Remote Login and key authentication before testing.
   - Prefer a VPN or trusted source-IP restrictions. Forwarding port 22 also
     exposes SSH, not just SFTP.

   **PAUSE A:** If the rule or firewall needs changing, explain the exact
   change and exposure, request approval, and wait. Have the user make any
   approved router change and confirm it before continuing.

   From an independent external network, have the user test:

   ```sh
   sftp -P 22 -i /path/to-matching-private-key username@84.246.243.130
   ```

   **PAUSE B:** Wait for the external test result. If it fails, report the
   error and check the forwarding rule, firewall, WAN address, and possible
   carrier-grade NAT. A successful LAN test does not verify public access.

## **1.4 Hosts-file aliases**

1. **Add the requested hosts entry** — On each LAN client that should use the
   aliases, verify the server's LAN IP and inspect existing hosts mappings.
   The requested entry is:

   ```text
   192.168.1.222   sftp-bens sftp-bens.local bennys-mac-mini bennys-mac-mini.local
   ```

   **PAUSE A:** Explain which client's hosts file needs changing and ask for
   approval. Wait. On a macOS client, have the user open:

   ```sh
   sudo nano /etc/hosts
   ```

   - The user enters any administrator password locally, never in chat.
   - Add the line once; preserve unrelated entries and resolve conflicting
     mappings for these names instead of adding duplicates.
   - Save with `Ctrl-O`, press Return, then exit with `Ctrl-X`.

   On Windows, have the user run Notepad as administrator, open
   `C:\Windows\System32\drivers\etc\hosts` (select **All files** in the Open
   dialog), add the line once, and save. They should enter any administrator
   credentials locally, never in chat.

   **PAUSE B:** Wait for the user to confirm the file was saved. On macOS,
   check name resolution with:

   ```sh
   dscacheutil -q host -a name sftp-bens
   ```

   On Windows, check each alias in PowerShell:

   ```powershell
   Test-NetConnection sftp-bens -Port 22
   ```

   Confirm `RemoteAddress` is `192.168.1.222` and
   `TcpTestSucceeded` is `True`. Repeat with each alias, then connect with
   `sftp username@sftp-bens`.

   Hosts entries affect only that client. The `.local` names can overlap
   with Bonjour/mDNS; investigate conflicting resolution rather than assume
   it works. These private-address aliases are for LAN/VPN access, not
   public internet access. On 2026-11-24, Windows alias setup was deferred;
   do not assume the aliases have been added to that client.

## **1.5 Windows client transfers**

1. **Connect from Windows** — In PowerShell, connect with the dedicated key:

   ```powershell
   sftp -o IdentitiesOnly=yes -o PreferredAuthentications=publickey -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no -i "$env:USERPROFILE\.ssh\id_ed25519_sftp" bennyskov@192.168.1.222
   ```

/Users/bennyskov/aeven/
   On 2026-11-24, the user confirmed a Windows connection, accepted the
   matching Ed25519 host fingerprint, and successfully listed the requested
   Mac directory. The observed fingerprint was
   `SHA256:9FMowzROBdxsa3zNiYV2eas26m4LPXZKF0XRdWlB94g`; verify it again on the
   Mac before trusting a first connection or a changed-key warning. This is a
   user-confirmed LAN test, not an external-access test.

2. **Upload a folder recursively** — From the connected `sftp>` prompt, change
   to the intended remote directory, then run:

   ```text
   cd "/Users/bennyskov/aeven/rhel-10.2-x86_64"
   lcd "C:\local_virtual_machines\rhel-10.2-x86_64"

   put -R * "/Users/bennyskov/aeven/rhel-10.2-x86_64"

   reput -R * "/Users/bennyskov/aeven/rhel-10.2-x86_64"
   ```

   Replace both paths. Quote paths containing spaces. `put -R` uploads the
   local folder and its contents into the current remote directory; it does
   not follow symbolic links. Confirm the local source and remote destination
   before starting a transfer. The command was checked against the installed
   OpenSSH `sftp` manual; this transfer has not yet been confirmed as run.
