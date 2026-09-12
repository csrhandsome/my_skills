# Clash TUN, DNS Hijack, and Fake-IP Notes

This is a plain knowledge note, not a Codex skill.

## What Happened

The failure was not primarily a broken Wi-Fi link. The Mac had:

- A valid Wi-Fi IP.
- A valid LAN gateway.
- A normal IPv4 default route after TUN was disabled.
- No system proxy residue in the failing off-state.

The breakage was at DNS resolution.

Observed failing pattern:

```text
System proxy: off
IPv4 route: default 192.168.0.1 en0
Wi-Fi IP: 192.168.0.108
DNS: 114.114.114.114
dscacheutil -q host -a name www.baidu.com: hangs
```

Observed recovered pattern:

```text
System proxy: off
DNS: 223.5.5.5 / 119.29.29.29
IPv4 route: default 192.168.0.1 en0
curl https://www.baidu.com: HTTP 200
```

Conclusion: the Mac was not "offline"; system DNS was stuck or unusable after Clash/TUN was disabled.

## DNS Path With Clash TUN

With Clash TUN enabled, DNS traffic can be captured by the TUN stack:

```yaml
tun:
  dns-hijack:
    - any:53
```

The path becomes:

```text
App asks: what is www.baidu.com?
  -> macOS sends DNS query
  -> DNS port 53 traffic is hijacked into Clash
  -> Clash resolves the domain using its configured DNS
  -> Clash returns an answer to the app
```

So while TUN is on, Clash can hide a broken system DNS because Clash is handling DNS itself.

## Fake-IP Mode

In fake-ip mode:

```yaml
dns:
  enhanced-mode: fake-ip
  fake-ip-range: 198.18.0.1/16
```

Clash does not necessarily return the real IP of a domain. It can return a synthetic IP from `198.18.0.0/16`.

Example:

```text
www.baidu.com -> 198.18.0.27
api.openai.com -> 198.18.0.68
```

These are not the real server IPs. They are placeholders understood by Clash.

The runtime mapping is:

```text
App connects to 198.18.0.27
  -> Clash sees 198.18.0.27
  -> Clash maps it back to www.baidu.com
  -> Clash applies rules
  -> Clash connects direct or through a proxy node
```

If TUN/Clash is disabled but the OS or browser still has a cached `198.18.x.x` answer, that fake IP no longer has meaning. Requests can fail even though the physical network is fine.

## What "DNS Hijacked By Clash" Means

It does not simply mean "Clash changed the DNS server."

More precisely:

1. Clash can modify the macOS system DNS setting.
2. Clash can hijack DNS packets in TUN mode.
3. Clash can answer DNS itself.
4. Clash can answer with fake IPs instead of real IPs.

That creates two different worlds:

```text
TUN on:
  App DNS -> Clash DNS -> fake-ip or real IP -> Clash routing

TUN off:
  App DNS -> macOS configured DNS -> real IP or timeout
```

If macOS falls back to a bad DNS server such as `114.114.114.114`, then turning TUN off makes the network appear dead.

## Why WeChat Could Still Work

WeChat may not rely entirely on the macOS system DNS resolver. It can use:

- HTTPDNS.
- Built-in server IP lists.
- Long-lived existing connections.
- Its own network fallback strategy.

Therefore, a broken system DNS can kill browsers, `curl`, npm, pip, and API clients while WeChat still works.

This is not contradictory. Different applications can use different name-resolution paths.

## Network Layer View

The failing state can be understood by layers:

```text
L2 Wi-Fi: OK
L3 IPv4 route: OK
L4 TCP: likely OK if connecting by IP
L7 DNS/name resolution: broken
Clash/TUN: masks the broken DNS while enabled
```

User-level symptom:

```text
DNS broken -> domains cannot become IPs -> web/API looks offline
```

## Practical Fix

Keep macOS Wi-Fi DNS independent and stable:

```text
223.5.5.5
119.29.29.29
```

During recovery, keep:

```text
TUN: optional/on if needed
System proxy: off when using TUN
Clash system DNS override: off
IPv6: off if Wi-Fi has no IPv6 router
```

Recovery commands:

```bash
networksetup -setwebproxystate Wi-Fi off
networksetup -setsecurewebproxystate Wi-Fi off
networksetup -setsocksfirewallproxystate Wi-Fi off
networksetup -setautoproxystate Wi-Fi off
networksetup -setdnsservers Wi-Fi 223.5.5.5 119.29.29.29
dscacheutil -flushcache
```

If allowed:

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

Expected healthy bare state:

```text
HTTPEnable: 0
HTTPSEnable: 0
SOCKSEnable: 0
DNS: 223.5.5.5 / 119.29.29.29
default route: Wi-Fi gateway on en0
curl: HTTP 200
```

