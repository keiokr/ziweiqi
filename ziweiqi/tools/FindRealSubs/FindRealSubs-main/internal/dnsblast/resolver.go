package dnsblast

import (
	"context"
	"fmt"
	"net"
	"sort"
	"strings"
	"time"

	"github.com/miekg/dns"
)

type Resolver struct {
	servers []string
	timeout time.Duration
	retries int
}

// ResolveInfo contains direct DNS evidence for one queried FQDN.
type ResolveInfo struct {
	Name   string   `json:"name"`
	CNAMEs []string `json:"cnames,omitempty"`
	IPs    []string `json:"ips,omitempty"`
	RCode  string   `json:"rcode,omitempty"`
	Error  string   `json:"error,omitempty"`
}

func (r ResolveInfo) Exists() bool {
	return len(r.CNAMEs) > 0 || len(r.IPs) > 0
}

func NewResolver(servers []string, timeout time.Duration, retries int) *Resolver {
	if timeout <= 0 {
		timeout = 3 * time.Second
	}
	if retries < 0 {
		retries = 0
	}
	return &Resolver{servers: normalizeDNSServers(servers), timeout: timeout, retries: retries}
}

func normalizeDNSServers(input []string) []string {
	if len(input) == 0 {
		input = []string{"223.5.5.5", "119.29.29.29", "8.8.8.8", "1.1.1.1"}
	}
	seen := make(map[string]struct{})
	var out []string
	for _, raw := range input {
		s := strings.TrimSpace(raw)
		if s == "" {
			continue
		}
		s = strings.TrimPrefix(strings.TrimPrefix(s, "udp://"), "tcp://")
		if _, _, err := net.SplitHostPort(s); err != nil {
			s = net.JoinHostPort(s, "53")
		}
		if _, ok := seen[s]; ok {
			continue
		}
		seen[s] = struct{}{}
		out = append(out, s)
	}
	if len(out) == 0 {
		out = []string{"223.5.5.5:53", "119.29.29.29:53", "8.8.8.8:53", "1.1.1.1:53"}
	}
	return out
}

func (r *Resolver) Resolve(ctx context.Context, name string) ResolveInfo {
	info := ResolveInfo{Name: strings.TrimSuffix(strings.ToLower(name), ".")}
	cnameSet := make(map[string]struct{})
	ipSet := make(map[string]struct{})
	var lastErr error
	for _, qtype := range []uint16{dns.TypeCNAME, dns.TypeA, dns.TypeAAAA} {
		msg, err := r.query(ctx, name, qtype)
		if err != nil {
			lastErr = err
			continue
		}
		info.RCode = dns.RcodeToString[msg.Rcode]
		for _, rr := range append(msg.Answer, msg.Extra...) {
			switch v := rr.(type) {
			case *dns.CNAME:
				c := normalizeDNSName(v.Target)
				if c != "" {
					cnameSet[c] = struct{}{}
				}
			case *dns.A:
				if v.A != nil {
					ipSet[v.A.String()] = struct{}{}
				}
			case *dns.AAAA:
				if v.AAAA != nil {
					ipSet[v.AAAA.String()] = struct{}{}
				}
			}
		}
	}
	for c := range cnameSet {
		info.CNAMEs = append(info.CNAMEs, c)
	}
	for ip := range ipSet {
		info.IPs = append(info.IPs, ip)
	}
	sort.Strings(info.CNAMEs)
	sort.Strings(info.IPs)
	if !info.Exists() && lastErr != nil {
		info.Error = lastErr.Error()
	}
	return info
}

func (r *Resolver) query(ctx context.Context, name string, qtype uint16) (*dns.Msg, error) {
	fqdn := dns.Fqdn(name)
	var lastErr error
	for attempt := 0; attempt <= r.retries; attempt++ {
		for _, server := range r.servers {
			m := new(dns.Msg)
			m.SetQuestion(fqdn, qtype)
			m.RecursionDesired = true
			c := &dns.Client{Net: "udp", Timeout: r.timeout}
			resp, _, err := c.ExchangeContext(ctx, m, server)
			if err == nil && resp != nil && resp.Truncated {
				c.Net = "tcp"
				resp, _, err = c.ExchangeContext(ctx, m, server)
			}
			if err != nil {
				lastErr = err
				continue
			}
			return resp, nil
		}
	}
	if lastErr == nil {
		lastErr = fmt.Errorf("dns query failed")
	}
	return nil, lastErr
}

func normalizeDNSName(s string) string {
	return strings.TrimSuffix(strings.ToLower(strings.TrimSpace(s)), ".")
}
