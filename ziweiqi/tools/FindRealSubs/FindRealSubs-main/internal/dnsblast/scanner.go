package dnsblast

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"sort"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

func Run(ctx context.Context, opts Options) (*ScanReport, error) {
	domains := normalizeDomains(opts.Domains)
	if len(domains) == 0 {
		return nil, fmt.Errorf("domain is required")
	}
	wordlist := uniqueLabels(opts.Wordlist)
	if len(wordlist) == 0 {
		return nil, fmt.Errorf("wordlist is required")
	}
	concurrency := opts.Concurrency
	if concurrency <= 0 {
		concurrency = 60
	}
	if concurrency > 1000 {
		concurrency = 1000
	}
	samples := opts.WildcardSamples
	if samples <= 0 {
		samples = 5
	}
	if samples > 20 {
		samples = 20
	}

	resolver := NewResolver(opts.DNSServers, opts.Timeout, opts.Retries)
	report := &ScanReport{StartedAt: time.Now(), Results: []Result{}}
	total := len(domains) * len(wordlist)
	report.Tested = total
	emit := func(e Event) {
		if opts.OnEvent != nil {
			opts.OnEvent(e)
		}
	}

	var done int64
	for _, domain := range domains {
		select {
		case <-ctx.Done():
			return report, ctx.Err()
		default:
		}
		emit(Event{Type: "log", Domain: domain, Message: fmt.Sprintf("[*] \u68c0\u6d4b\u6cdb\u89e3\u6790: %s", domain), Done: int(done), Total: total})
		wild := DetectWildcard(ctx, resolver, domain, samples)
		report.Wildcards = append(report.Wildcards, wild)
		if wild.Exists {
			emit(Event{Type: "log", Domain: domain, Message: fmt.Sprintf("[!] \u5b58\u5728\u6cdb\u89e3\u6790: CNAME\u6807\u5fd7=%s IP\u6807\u5fd7=%s", emptyDash(wild.CNAMEFlag), strings.Join(wild.IPs, ",")), Done: int(done), Total: total})
		} else {
			skipped := int(atomic.AddInt64(&done, int64(len(wordlist))))
			emit(Event{Type: "log", Domain: domain, Message: "[SKIP] \u672a\u53d1\u73b0\u6cdb\u89e3\u6790\uff1a\u5f53\u524d\u4e3a\u6cdb\u89e3\u6790\u57df\u540d\u4e13\u7528\u6a21\u5f0f\uff0c\u5df2\u8df3\u8fc7", Done: skipped, Total: total})
			emit(Event{Type: "progress", Domain: domain, Done: skipped, Total: total})
			continue
		}

		var httpVerifier *HTTPVerifier
		if opts.HTTPVerify {
			httpVerifier = NewHTTPVerifier(ctx, domain, wild, opts.Timeout)
			emit(Event{Type: "log", Domain: domain, Message: fmt.Sprintf("[*] \u534f\u8bae\u9884\u5224: %s\uff0c\u5f53\u524d\u534f\u8bae=%s", httpVerifier.PortInfo(), strings.Join(httpVerifier.Schemes(), "+")), Done: int(done), Total: total})
			emit(Event{Type: "log", Domain: domain, Message: fmt.Sprintf("[*] HTTP\u4e8c\u6b21\u9a8c\u8bc1\u5df2\u542f\u7528\uff0c\u6cdb\u89e3\u6790HTTP\u57fa\u7ebf=%d", httpVerifier.BaselineCount()), Done: int(done), Total: total})
			if opts.FastWildcardHTTP {
				emit(Event{Type: "log", Domain: domain, Message: "[*] \u6cdb\u89e3\u6790\u4e13\u7528\u6a21\u5f0f\uff1a\u8df3\u8fc7\u9010\u4e2aDNS\u67e5\u8be2\uff0c\u4f7f\u7528\u5185\u7f6eHTTP\u54cd\u5e94\u5dee\u5f02\u7206\u7834", Done: int(done), Total: total})
			}
		}

		jobs := make(chan string)
		var wg sync.WaitGroup
		var mu sync.Mutex
		for i := 0; i < concurrency; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				for label := range jobs {
					fqdn := label + "." + domain
					if httpVerifier != nil && opts.FastWildcardHTTP {
						if res := httpVerifier.VerifyResult(ctx, domain, fqdn, nil, wild.IPs); res != nil {
							mu.Lock()
							report.Results = append(report.Results, *res)
							mu.Unlock()
							emit(Event{Type: "found", Domain: domain, Message: formatFoundResult(res), Result: res})
						} else {
							atomic.AddInt64(&report.Filtered, 1)
							if opts.ShowFiltered {
								emit(Event{Type: "filtered", Domain: domain, Message: fmt.Sprintf("[WILDCARD] %s \u88ab\u6cdb\u89e3\u6790HTTP\u57fa\u7ebf\u8fc7\u6ee4", fqdn)})
							}
						}
						d := int(atomic.AddInt64(&done, 1))
						emit(Event{Type: "progress", Domain: domain, Done: d, Total: total})
						continue
					}

					info := resolver.Resolve(ctx, fqdn)
					if info.Error != "" && !info.Exists() {
						atomic.AddInt64(&report.Errors, 1)
					}
					if res, filtered := classify(domain, fqdn, info, wild); res != nil {
						if httpVerifier != nil {
							if httpRes := httpVerifier.VerifyResult(ctx, domain, fqdn, info.CNAMEs, info.IPs); httpRes != nil {
								res = httpRes
							}
						}
						mu.Lock()
						report.Results = append(report.Results, *res)
						mu.Unlock()
						emit(Event{Type: "found", Domain: domain, Message: formatFoundResult(res), Result: res})
					} else if filtered {
						if httpVerifier != nil {
							if res := httpVerifier.VerifyResult(ctx, domain, fqdn, info.CNAMEs, info.IPs); res != nil {
								mu.Lock()
								report.Results = append(report.Results, *res)
								mu.Unlock()
								emit(Event{Type: "found", Domain: domain, Message: formatFoundResult(res), Result: res})
								d := int(atomic.AddInt64(&done, 1))
								emit(Event{Type: "progress", Domain: domain, Done: d, Total: total})
								continue
							}
						}
						atomic.AddInt64(&report.Filtered, 1)
						if opts.ShowFiltered {
							emit(Event{Type: "filtered", Domain: domain, Message: fmt.Sprintf("[WILDCARD] %s \u88ab\u6cdb\u89e3\u6790\u8fc7\u6ee4", fqdn)})
						}
					}
					d := int(atomic.AddInt64(&done, 1))
					emit(Event{Type: "progress", Domain: domain, Done: d, Total: total})
				}
			}()
		}
		for _, label := range wordlist {
			select {
			case <-ctx.Done():
				close(jobs)
				wg.Wait()
				return report, ctx.Err()
			case jobs <- label:
			}
		}
		close(jobs)
		wg.Wait()
	}

	sort.Slice(report.Results, func(i, j int) bool { return report.Results[i].Subdomain < report.Results[j].Subdomain })
	report.FinishedAt = time.Now()
	emit(Event{Type: "done", Message: fmt.Sprintf("\u5b8c\u6210\uff1a\u53d1\u73b0 %d \u4e2a\uff0c\u6cdb\u89e3\u6790\u8fc7\u6ee4 %d \u4e2a", len(report.Results), report.Filtered), Done: total, Total: total})
	return report, nil
}

func DetectWildcard(ctx context.Context, resolver *Resolver, domain string, sampleCount int) WildcardReport {
	report := WildcardReport{
		Domain:        domain,
		SampleCount:   sampleCount,
		MatchStrategy: "多随机样本 + CNAME标志优先 + A/AAAA集合兜底比对",
	}
	cnameSet := make(map[string]struct{})
	ipSet := make(map[string]struct{})
	for i := 0; i < sampleCount; i++ {
		label := "fs-nx-" + randomHex(8) + fmt.Sprintf("-%02d", i)
		info := resolver.Resolve(ctx, label+"."+domain)
		if !info.Exists() {
			continue
		}
		report.Exists = true
		report.Samples = append(report.Samples, info)
		for _, c := range info.CNAMEs {
			if report.CNAMEFlag == "" {
				report.CNAMEFlag = c
			}
			cnameSet[c] = struct{}{}
		}
		for _, ip := range info.IPs {
			ipSet[ip] = struct{}{}
		}
	}
	report.CNAMEs = sortedKeys(cnameSet)
	report.IPs = sortedKeys(ipSet)
	return report
}

func classify(domain, fqdn string, info ResolveInfo, wild WildcardReport) (*Result, bool) {
	if !info.Exists() {
		return nil, false
	}
	res := &Result{Domain: domain, Subdomain: normalizeDNSName(fqdn), CNAMEs: info.CNAMEs, IPs: info.IPs}
	if !wild.Exists {
		res.Reason = "无泛解析，目标存在 A/AAAA/CNAME 记录"
		return res, false
	}
	if wildcardLike(info, wild) {
		return nil, true
	}
	// When wildcard has no CNAME and random samples already show rotating /
	// label-dependent IPs, an IP-only mismatch is not reliable evidence. This
	// avoids the common false positive pattern where every nonexistent label
	// receives a different parking/hijack IP.
	if len(info.CNAMEs) == 0 && len(wild.CNAMEs) == 0 && wildcardHasRotatingIPOnly(wild) {
		return nil, true
	}
	if len(info.CNAMEs) > 0 && !allIn(info.CNAMEs, toSet(wild.CNAMEs)) {
		res.Reason = "CNAME 与泛解析标志不同"
	} else if len(info.IPs) > 0 && !allIn(info.IPs, toSet(wild.IPs)) {
		res.Reason = "A/AAAA 记录与泛解析样本集合不同"
	} else {
		res.Reason = "解析签名与泛解析样本不同"
	}
	return res, false
}

func wildcardLike(info ResolveInfo, wild WildcardReport) bool {
	if !wild.Exists || !info.Exists() {
		return false
	}
	for _, sample := range wild.Samples {
		if sameStringSlice(info.CNAMEs, sample.CNAMEs) && sameStringSlice(info.IPs, sample.IPs) {
			return true
		}
	}
	wildCNAMEs := toSet(wild.CNAMEs)
	if len(info.CNAMEs) > 0 && len(wildCNAMEs) > 0 && allIn(info.CNAMEs, wildCNAMEs) {
		return true
	}
	wildIPs := toSet(wild.IPs)
	if len(info.IPs) > 0 && len(wildIPs) > 0 && allIn(info.IPs, wildIPs) {
		return true
	}
	return false
}

func wildcardHasRotatingIPOnly(wild WildcardReport) bool {
	if len(wild.CNAMEs) > 0 || len(wild.Samples) < 2 {
		return false
	}
	signatures := make(map[string]struct{})
	for _, sample := range wild.Samples {
		if len(sample.CNAMEs) > 0 || len(sample.IPs) == 0 {
			continue
		}
		signatures[strings.Join(sample.IPs, ",")] = struct{}{}
	}
	return len(signatures) > 1
}

func normalizeDomains(input []string) []string {
	seen := make(map[string]struct{})
	var out []string
	for _, raw := range input {
		for _, part := range strings.FieldsFunc(raw, func(r rune) bool { return r == ',' || r == ';' || r == '\n' || r == '\r' || r == '\t' || r == ' ' }) {
			d := strings.TrimSpace(strings.ToLower(part))
			d = strings.TrimPrefix(strings.TrimPrefix(d, "https://"), "http://")
			if i := strings.IndexAny(d, "/:"); i >= 0 {
				d = d[:i]
			}
			d = strings.Trim(d, ".")
			if d == "" || strings.Contains(d, "..") {
				continue
			}
			if _, ok := seen[d]; ok {
				continue
			}
			seen[d] = struct{}{}
			out = append(out, d)
		}
	}
	return out
}

func uniqueLabels(input []string) []string {
	seen := make(map[string]struct{})
	var out []string
	for _, raw := range input {
		label := strings.Trim(strings.ToLower(strings.TrimSpace(raw)), ".")
		if !validLabel(label) {
			continue
		}
		if _, ok := seen[label]; ok {
			continue
		}
		seen[label] = struct{}{}
		out = append(out, label)
	}
	return out
}

func randomHex(n int) string {
	b := make([]byte, n)
	if _, err := rand.Read(b); err != nil {
		return fmt.Sprintf("%d", time.Now().UnixNano())
	}
	return hex.EncodeToString(b)
}

func toSet(items []string) map[string]struct{} {
	m := make(map[string]struct{}, len(items))
	for _, item := range items {
		m[item] = struct{}{}
	}
	return m
}

func allIn(items []string, set map[string]struct{}) bool {
	if len(items) == 0 || len(set) == 0 {
		return false
	}
	for _, item := range items {
		if _, ok := set[item]; !ok {
			return false
		}
	}
	return true
}

func sameStringSlice(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

func sortedKeys(m map[string]struct{}) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}

func emptyDash(s string) string {
	if s == "" {
		return "-"
	}
	return s
}
