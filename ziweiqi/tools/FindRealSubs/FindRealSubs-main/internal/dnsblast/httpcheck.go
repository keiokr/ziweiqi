package dnsblast

import (
	"context"
	"crypto/sha1"
	"crypto/tls"
	"fmt"
	"io"
	"net/http"
	"regexp"
	"strings"
	"sync"
	"time"
)

type HTTPVerifier struct {
	baselines []HTTPSignature
	timeout   time.Duration
	mu        sync.RWMutex
	schemes   []string
	locked    bool
}

type HTTPSignature struct {
	Scheme   string
	Host     string
	Status   int
	Title    string
	Location string
	Len      int
	Hash     string
	Error    string
}

var titleRe = regexp.MustCompile(`(?is)<title[^>]*>(.*?)</title>`)

func NewHTTPVerifier(ctx context.Context, domain string, wild WildcardReport, timeout time.Duration) *HTTPVerifier {
	if !wild.Exists {
		return nil
	}
	if timeout <= 0 {
		timeout = 3 * time.Second
	}
	if timeout > 5*time.Second {
		timeout = 5 * time.Second
	}
	v := &HTTPVerifier{timeout: timeout}
	hosts := make([]string, 0, 3)
	for _, sample := range wild.Samples {
		if sample.Name != "" {
			hosts = append(hosts, sample.Name)
		}
		if len(hosts) >= 3 {
			break
		}
	}
	for len(hosts) < 3 {
		hosts = append(hosts, "fs-http-nx-"+randomHex(6)+"."+domain)
	}
	for _, host := range hosts {
		v.baselines = append(v.baselines, v.probeHost(ctx, host)...)
	}
	v.schemes = schemesFromBaselines(v.baselines)
	if len(v.schemes) == 0 {
		v.schemes = []string{"http", "https"}
	}
	if len(v.schemes) == 1 {
		v.locked = true
	}
	return v
}

func (v *HTTPVerifier) BaselineCount() int {
	if v == nil {
		return 0
	}
	return len(v.baselines)
}

func (v *HTTPVerifier) Schemes() []string {
	if v == nil {
		return nil
	}
	v.mu.RLock()
	defer v.mu.RUnlock()
	return append([]string(nil), v.schemes...)
}

func (v *HTTPVerifier) PortInfo() string {
	schemes := v.Schemes()
	hasHTTP := containsString(schemes, "http")
	hasHTTPS := containsString(schemes, "https")
	switch {
	case hasHTTP && hasHTTPS:
		return "80=open 443=open"
	case hasHTTP:
		return "80=open 443=closed"
	case hasHTTPS:
		return "80=closed 443=open"
	default:
		return "80=unknown 443=unknown"
	}
}

func (v *HTTPVerifier) VerifyResult(ctx context.Context, domain, host string, cnames, ips []string) *Result {
	if v == nil {
		return nil
	}
	seen := false
	for _, scheme := range v.Schemes() {
		sig := v.probeURL(ctx, scheme, host)
		if sig.Error != "" {
			continue
		}
		seen = true
		if len(v.baselines) == 0 {
			if isGenericErrorStatus(sig.Status) && isGenericErrorTitle(sig.Title) {
				continue
			}
			v.lockScheme(sig.Scheme)
			return resultFromHTTPSignature(domain, host, cnames, ips, sig)
		}
		if wildcardErrorLike(sig, v.baselines) {
			continue
		}
		if !v.matchesAnyBaseline(sig) {
			v.lockScheme(sig.Scheme)
			return resultFromHTTPSignature(domain, host, cnames, ips, sig)
		}
	}
	if !seen {
		return nil
	}
	return nil
}

func (v *HTTPVerifier) matchesAnyBaseline(sig HTTPSignature) bool {
	for _, base := range v.baselines {
		if base.Error != "" || base.Scheme != sig.Scheme {
			continue
		}
		if httpSimilar(base, sig) {
			return true
		}
	}
	return false
}

func (v *HTTPVerifier) lockScheme(scheme string) {
	if scheme != "http" && scheme != "https" {
		return
	}
	v.mu.Lock()
	defer v.mu.Unlock()
	if v.locked && len(v.schemes) == 1 && v.schemes[0] == scheme {
		return
	}
	v.schemes = []string{scheme}
	v.locked = true
}

func schemesFromBaselines(baselines []HTTPSignature) []string {
	seen := make(map[string]struct{})
	for _, base := range baselines {
		if base.Error == "" && (base.Scheme == "http" || base.Scheme == "https") {
			seen[base.Scheme] = struct{}{}
		}
	}
	var out []string
	if _, ok := seen["http"]; ok {
		out = append(out, "http")
	}
	if _, ok := seen["https"]; ok {
		out = append(out, "https")
	}
	return out
}

func containsString(items []string, want string) bool {
	for _, item := range items {
		if item == want {
			return true
		}
	}
	return false
}

func resultFromHTTPSignature(domain, host string, cnames, ips []string, sig HTTPSignature) *Result {
	title := strings.TrimSpace(sig.Title)
	if title == "" {
		title = "-"
	}
	url := sig.Scheme + "://" + normalizeDNSName(host)
	return &Result{
		Domain:    domain,
		Subdomain: normalizeDNSName(host),
		URL:       url,
		Scheme:    sig.Scheme,
		CNAMEs:    append([]string(nil), cnames...),
		IPs:       append([]string(nil), ips...),
		Status:    sig.Status,
		Title:     title,
		Length:    sig.Len,
		Reason:    fmt.Sprintf("标题：%s；长度：%d；状态码=%d", title, sig.Len, sig.Status),
	}
}

func formatFoundResult(res *Result) string {
	if res == nil {
		return ""
	}
	url := res.URL
	if url == "" {
		url = res.Subdomain
	}
	title := strings.TrimSpace(res.Title)
	if title == "" {
		title = "-"
	}
	return fmt.Sprintf("发现：%s，标题：%s；长度：%d；状态码=%d", url, title, res.Length, res.Status)
}

func httpSimilar(a, b HTTPSignature) bool {
	if a.Status != b.Status {
		return false
	}
	titleA := normalizeTitle(a.Title)
	titleB := normalizeTitle(b.Title)
	if titleA != titleB {
		return false
	}
	diff := a.Len - b.Len
	if diff < 0 {
		diff = -diff
	}
	if diff == 0 {
		return true
	}
	if isGenericErrorStatus(a.Status) && isGenericErrorTitle(titleA) && diff <= 800 {
		return true
	}
	if a.Location != b.Location {
		return false
	}
	if a.Hash != "" && b.Hash != "" && a.Hash == b.Hash {
		return true
	}
	limit := 300
	if a.Len > 0 {
		byRatio := a.Len / 10
		if byRatio > limit {
			limit = byRatio
		}
	}
	return diff <= limit
}

func isGenericErrorStatus(status int) bool {
	return status == 400 || status == 401 || status == 403 || status == 404 || status == 405 || status == 408 || status == 429 || status == 500 || status == 502 || status == 503 || status == 504
}

func isGenericErrorTitle(title string) bool {
	title = normalizeTitle(title)
	if title == "" {
		return true
	}
	generic := []string{"404", "404 not found", "not found", "403 forbidden", "forbidden", "bad request", "error", "nginx error", "service unavailable", "502 bad gateway", "503 service temporarily unavailable"}
	for _, item := range generic {
		if title == item || strings.Contains(title, item) {
			return true
		}
	}
	return false
}

func wildcardErrorLike(sig HTTPSignature, bases []HTTPSignature) bool {
	if !isGenericErrorStatus(sig.Status) || !isGenericErrorTitle(sig.Title) {
		return false
	}
	for _, base := range bases {
		if base.Scheme != sig.Scheme || base.Status != sig.Status {
			continue
		}
		if normalizeTitle(base.Title) != normalizeTitle(sig.Title) {
			continue
		}
		diff := base.Len - sig.Len
		if diff < 0 {
			diff = -diff
		}
		if diff <= 1200 {
			return true
		}
	}
	return false
}

func (v *HTTPVerifier) probeHost(ctx context.Context, host string) []HTTPSignature {
	var out []HTTPSignature
	for _, scheme := range []string{"http", "https"} {
		sig := v.probeURL(ctx, scheme, host)
		if sig.Error == "" {
			out = append(out, sig)
		}
	}
	return out
}

func (v *HTTPVerifier) probeURL(ctx context.Context, scheme, host string) HTTPSignature {
	ctx, cancel := context.WithTimeout(ctx, v.timeout)
	defer cancel()
	sig := HTTPSignature{Scheme: scheme, Host: host}
	tr := &http.Transport{TLSClientConfig: &tls.Config{InsecureSkipVerify: true}, Proxy: nil}
	client := &http.Client{Transport: tr, Timeout: v.timeout, CheckRedirect: func(req *http.Request, via []*http.Request) error {
		if len(via) >= 3 {
			return http.ErrUseLastResponse
		}
		return nil
	}}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, scheme+"://"+host+"/", nil)
	if err != nil {
		sig.Error = err.Error()
		return sig
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 FindSubs")
	req.Header.Set("Accept", "text/html,*/*;q=0.8")
	resp, err := client.Do(req)
	if err != nil {
		sig.Error = err.Error()
		return sig
	}
	defer resp.Body.Close()
	sig.Status = resp.StatusCode
	if loc := resp.Header.Get("Location"); loc != "" {
		sig.Location = normalizeLocation(loc)
	}
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 65536))
	sig.Len = len(body)
	sig.Title = extractTitle(string(body))
	sum := sha1.Sum([]byte(normalizeBody(string(body))))
	sig.Hash = fmt.Sprintf("%x", sum[:])
	return sig
}

func extractTitle(body string) string {
	m := titleRe.FindStringSubmatch(body)
	if len(m) < 2 {
		return ""
	}
	return strings.Join(strings.Fields(htmlUnescape(m[1])), " ")
}

func normalizeTitle(s string) string {
	return strings.ToLower(strings.Join(strings.Fields(s), " "))
}

func normalizeBody(s string) string {
	s = strings.ToLower(s)
	s = regexp.MustCompile(`\d{5,}`).ReplaceAllString(s, "0")
	s = regexp.MustCompile(`\s+`).ReplaceAllString(s, " ")
	if len(s) > 8192 {
		s = s[:8192]
	}
	return s
}

func normalizeLocation(s string) string {
	s = strings.TrimSpace(strings.ToLower(s))
	if i := strings.Index(s, "?"); i >= 0 {
		s = s[:i]
	}
	return s
}

func htmlUnescape(s string) string {
	replacer := strings.NewReplacer("&amp;", "&", "&lt;", "<", "&gt;", ">", "&quot;", `"`, "&#39;", "'")
	return replacer.Replace(s)
}
