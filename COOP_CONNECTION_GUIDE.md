# ZeroTier co-op connection

Player connections currently use a private ZeroTier network only. Public-IP
connections are unsupported. Co-op remains hidden in release builds until live
gameplay verification passes; developer builds set `COOP_FEATURE_ENABLED = True`
in `randomizer/coop/feature.py` on both computers.

## Connect two PCs

1. Install ZeroTier on both PCs, create one private network, join it on both
   PCs and authorize both devices. Use the
   [official setup guide](https://docs.zerotier.com/start/).
2. Use matching Mental Omega installations and updated launchers. In
   **Settings**, find the co-op controls below Rainbowizer in **Mission
   Appearance** (or in **Shop Setup** for Shop Mode). Enable **Co-op mode
   (experimental)**; **Players** shows the supported count of **2**. Give
   each player a different name in the connection dialog. The dialog also
   opens before enabling co-op; connecting requires co-op mode.
3. Generate the Grid on the host. For Shop, **both players select Shop Mode**,
   enable co-op, and start separate runs with the same seed and stage before
   connecting; each player retains their own profile and purchases. Joining a
   Shop host from Grid Mode opens Shop Setup with the host's seed and explains
   the required setup. Start the guest run, then reconnect. An existing active
   guest run is preserved and its seed input is not replaced.
4. Click **Co-op Connection…**. The host selects **Host**, copies its displayed
   pairing code, shares it privately and clicks **Connect**. Hosts do not enter
   an IP address.
5. The guest selects **Join**, pastes the host's **ZeroTier Managed IPv4** and
   pairing code, then clicks **Connect**. Use the IPv4 without its subnet suffix,
   port, URL or network ID. Both inputs accept paste while masked.
6. Wait for the connected status. Host selects and launches the mission; the
   guest can suggest missions. A working lobby does not verify native gameplay.

Grid rewards are shared: both players receive the same unlocked units, buffs,
buildings, and earned powers on future mission launches. Powers use separate
hidden providers for the two native player slots, including Chronolift and
Time Freeze. Update both launchers together and reconnect; existing Grid
progress and unlocked rewards are retained. Shop purchases remain private.

Generated co-op maps disable the cosmetic `BEHIND` marker. Windows/Linux
desync logs showed that a hidden reward provider could create this animation
on only one client, shifting later object IDs and checksums. Both players must
update and reconnect to regenerate the map; sustained native gameplay still
needs verification. This change applies to both Grid and Shop maps.

The ports are automatic: host TCP `19420` for the lobby, host TCP `19421` for
game preparation, and UDP `1234` on both PCs. If the PC firewall blocks the
connection, allow this traffic over the private ZeroTier interface. ZeroTier
normally avoids router forwarding; it still requires local firewall permission.
See [ZeroTier firewall guidance](https://docs.zerotier.com/routertips/).

## Private fields and diagnostics

The host pairing code is a visible, noneditable label. Each launcher retains
its own host code and the separately entered guest code while open. **Copy
pairing code** copies whichever role is selected. Guest IP/code inputs are
masked by default; **Show IP and code (visible on stream)** reveals them until
unchecked, copied or closing the dialog. Host labels remain visible. Closing
the dialog keeps the connection open; close the game and click **Disconnect** to reconnect
or change settings.

**Show connection log** displays connection stages, synchronization and launch
failures. **Copy connection log** copies the displayed log. Connection messages
redact IPs and pairing codes. Native `spawn.ini`, game logs and clipboard history
can still contain addresses. The persistent launcher log is
`RandomizerLauncherData/logs/launcher.log` in packaged builds, or
`RandomizerLauncher/logs/launcher.log` in source launches.

If **Mental Omega runtime differs** appears, compare the listed game files.
Both local and remote manifests include normalized and raw SHA-256 hashes in
the connection log. Version, co-op difficulty INIs and optional loose rules/art
ignore CRLF/LF differences. Native binaries, including optional Phobos, must
match exactly. Missing versus installed optional files also differ. Player
saves and configuration folders are excluded. Selected native co-op maps use
normalized source hashes and case-independent filenames; prepared game maps
still require byte-identical SHA-256 and matching spawn metadata.
Native co-op catalogue rows also match, including enemy positions and player
restrictions; generated lobby entries are ignored when comparing that catalogue.

Old launcher protocols are rejected with an update message. Update both
launchers together. Existing saved runs are retained; previous connection
choices migrate to ZeroTier.

If connecting times out, check that the host is waiting, both ZeroTier devices
are authorized, the guest used the host's Managed IPv4 and host TCP `19420` is
reachable. Wait for **Co-op lobby listening on TCP 19420** in the host log
before the guest clicks **Connect**. The guest retries refused connections
and individual socket timeouts within a 30-second window; persistent blocked
traffic still requires fixing the network or host firewall.

While the host is listening, Windows guests can test the actual lobby port in
PowerShell (replace the placeholder with the host's ZeroTier Managed IPv4):

```powershell
Test-NetConnection -ComputerName 'HOST_ZEROTIER_IPV4' -Port 19420
```

`TcpTestSucceeded: False` means that the lobby port could not be reached.
The test opens a TCP connection without the launcher handshake; the host may
log a peer disconnect afterward. Click **Disconnect**, then **Connect** on
the host before trying Join again. See Microsoft's
[Test-NetConnection documentation](https://learn.microsoft.com/en-us/powershell/module/nettcpip/test-netconnection).

If the lobby connects but preparation fails, check TCP `19421`.
If both games start but cannot play together, check UDP `1234` on both PCs and
record the mission, seed, platform, connection log and native game logs.

Developer loopback diagnostics can still use `127.0.0.1` with separate game
folders and Wine prefixes. The guest uses UDP `1235` automatically there. These
checks do not establish that Linux/Windows gameplay works over ZeroTier.
