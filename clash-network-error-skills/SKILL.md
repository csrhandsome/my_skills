---
name: clash-network-error-skills
description: Diagnose and recover macOS network failures caused by Clash Verge Rev, Mihomo, TUN mode, system proxy, DNS override, fake-ip, or 198.18.x.x routes. Use when the user says the Mac only has network with Clash/TUN enabled, closing TUN/proxy breaks browsers or API requests, WeChat still works while web/API does not, DNS seems polluted, or Clash cannot restore network after exit.
---

# Clash Network Error Skills

Use this skill for macOS network incidents involving Clash Verge Rev / Mihomo / Clash, especially when:
- TUN must stay on or the Mac has no network.
- Closing TUN/proxy makes browsers, curl, npm, pip, or API clients fail.
- WeChat or some native apps work but web/API requests do not.
- DNS results include `198.18.x.x` fake IPs.
- System proxy points to `127.0.0.1:7890`, `7897`, or another local Clash port.
- Wi-Fi seems "broken" only after Clash exits.

The core goal is to separate four layers: physical Wi-Fi, IPv4 route, system proxy, and DNS/fake-ip state.

## Safety Rules

- Do not repeatedly ask the user to turn TUN off while you are relying on the same network connection; this can disconnect the session.
- First collect state while Clash/TUN is on, then use a rescue script or explicit commands for the off-state.
- Avoid destructive network resets until simple proxy/DNS recovery has been tried.
- Treat `198.18.0.0/16` as Clash fake-ip space. It is useful only while Clash is running and mapping fake IPs back to domains.

## Fast Diagnosis

Run these first:

```bash
scutil --proxy
scutil --dns
networksetup -getdnsservers Wi-Fi
networksetup -getwebproxy Wi-Fi
networksetup -getsecurewebproxy Wi-Fi
networksetup -getsocksfirewallproxy Wi-Fi
networksetup -getinfo Wi-Fi
netstat -rn
dscacheutil -q host -a name www.baidu.com
curl -I --connect-timeout 8 https://www.baidu.com
```

If sandboxed commands fail, rerun read-only checks with appropriate approval.

## How To Interpret

Wi-Fi is probably healthy if:

```text
IP address: 192.168.x.x or 10.x.x.x
Router: <LAN gateway>
default <LAN gateway> en0
```

System proxy residue is present if `scutil --proxy` shows:

```text
HTTPEnable : 1
HTTPProxy : 127.0.0.1
HTTPPort : 7897
HTTPSEnable : 1
SOCKSEnable : 1
```

If Clash is closed while these are enabled, browsers and many API clients will connect to a dead local proxy and appear offline.

TUN / fake-ip route capture is present if `netstat -rn` shows routes like:

```text
1          198.18.0.1  utun4
2/7        198.18.0.1  utun4
128.0/1    198.18.0.1  utun4
198.18.0.1 198.18.0.1  utun4
```

DNS/fake-ip residue is present if host lookups return:

```text
www.baidu.com -> 198.18.x.x
api.openai.com -> 198.18.x.x
```

After TUN is off, these fake IPs cannot work unless Clash is still intercepting them.

DNS resolver failure is likely if:
- System proxy is off.
- IPv4 default route is the Wi-Fi gateway.
- `dscacheutil -q host ...` hangs or returns nothing.
- `scutil --dns` points to a bad single DNS such as `114.114.114.114`.

In this case the network is not "dead"; name resolution is dead. Apps using HTTPDNS, long-lived sockets, or IP-direct paths may still work, which explains why WeChat can work while browsers/API clients fail.

## Recovery Commands

Use these to restore bare Wi-Fi network on macOS:

```bash
networksetup -setwebproxystate Wi-Fi off
networksetup -setsecurewebproxystate Wi-Fi off
networksetup -setsocksfirewallproxystate Wi-Fi off
networksetup -setautoproxystate Wi-Fi off
networksetup -setdnsservers Wi-Fi 223.5.5.5 119.29.29.29
dscacheutil -flushcache
```

If allowed, also reload mDNSResponder:

```bash
sudo killall -HUP mDNSResponder
```

Verify:

```bash
scutil --proxy
scutil --dns
netstat -rn
curl -I --connect-timeout 8 https://www.baidu.com
```

Healthy bare state should look like:

```text
HTTPEnable : 0
HTTPSEnable : 0
SOCKSEnable : 0
nameserver[0] : 223.5.5.5
nameserver[1] : 119.29.29.29
default <LAN gateway> en0
HTTP/1.1 200 OK
```

## Clash Verge Recommendations

For stability during recovery:

- TUN: on if needed.
- System proxy: off when TUN is on.
- DNS override / system DNS setting: off until bare network is proven stable.
- macOS Wi-Fi DNS: manually set to `223.5.5.5` and `119.29.29.29`.
- IPv6: off if Wi-Fi has no IPv6 router.

Recommended DNS section while diagnosing:

```yaml
dns:
  enable: true
  listen: ':53'
  enhanced-mode: fake-ip
  fake-ip-range: '198.18.0.1/16'
  ipv6: false
  default-nameserver:
    - '223.5.5.5'
    - '119.29.29.29'
  nameserver:
    - 'https://dns.alidns.com/dns-query'
    - 'https://doh.pub/dns-query'
  proxy-server-nameserver:
    - 'https://dns.alidns.com/dns-query'
    - 'https://doh.pub/dns-query'
    - 'tls://223.5.5.5'
```

If fake-ip residue remains a problem, temporarily test:

```yaml
dns:
  enhanced-mode: redir-host
  ipv6: false
```

This reduces fake-ip cache issues at the cost of weaker DNS-based behavior.

Also check top-level Clash config, not only `dns.ipv6`:

```yaml
ipv6: false
```

## Off-State Capture Workflow

If closing TUN disconnects the agent, use the bundled script:

```bash
scripts/clash_network_rescue.sh
```

Ask the user to run it from the skill directory, or run it directly by absolute path when available. It accepts an optional network service name, defaulting to `Wi-Fi`:

```bash
./scripts/clash_network_rescue.sh
./scripts/clash_network_rescue.sh "USB 10/100/1000 LAN"
```

The script:

1. Logs `scutil --proxy`, `scutil --dns`, `networksetup -getdnsservers`, `networksetup -getinfo`, and `netstat -rn`.
2. Runs DNS probes with hard timeouts so it cannot hang indefinitely on `dscacheutil`.
3. Disables system HTTP/HTTPS/SOCKS/PAC proxies.
4. Sets stable DNS to `223.5.5.5 119.29.29.29`.
5. Flushes DNS cache and attempts to reload `mDNSResponder`.
6. Tests gateway, DNS IP, and HTTPS.

Logs are written to the user's Desktop as `clash-network-YYYYMMDD-HHMMSS.log`.

If a script stops at `dscacheutil -q host ...`, interpret that as evidence that macOS DNS resolution is hanging in the off-state.

## Canonical Case Pattern

Observed failing state:

```text
System proxy: off
IPv4 route: default 192.168.0.1 en0
Wi-Fi IP: 192.168.0.x
DNS: 114.114.114.114
dscacheutil -q host -a name www.baidu.com: hangs
```

Observed recovered state:

```text
System proxy: off
DNS: 223.5.5.5 / 119.29.29.29
IPv4 route: default 192.168.0.1 en0
curl https://www.baidu.com: HTTP 200
```

Conclusion for this pattern: Wi-Fi is healthy; the failure is macOS system DNS state after Clash/TUN exit. Keep Clash from writing system DNS back to the bad resolver.
