package dnsblast

import "time"

// Options describes a DNS brute-force scan.
type Options struct {
	Domains          []string
	Wordlist         []string
	DNSServers       []string
	Concurrency      int
	Timeout          time.Duration
	Retries          int
	WildcardSamples  int
	ShowFiltered     bool
	HTTPVerify       bool
	FastWildcardHTTP bool
	OnEvent          func(Event)
}

// Event is emitted while a scan is running. It is intentionally JSON-friendly
// so both CLI and GUI frontends can stream the same scan state.
type Event struct {
	Type    string  `json:"type"`
	Message string  `json:"message,omitempty"`
	Domain  string  `json:"domain,omitempty"`
	Done    int     `json:"done,omitempty"`
	Total   int     `json:"total,omitempty"`
	Result  *Result `json:"result,omitempty"`
}

// Result is a confirmed subdomain after wildcard filtering.
type Result struct {
	Domain    string   `json:"domain"`
	Subdomain string   `json:"subdomain"`
	URL       string   `json:"url,omitempty"`
	Scheme    string   `json:"scheme,omitempty"`
	CNAMEs    []string `json:"cnames,omitempty"`
	IPs       []string `json:"ips,omitempty"`
	Status    int      `json:"status,omitempty"`
	Title     string   `json:"title,omitempty"`
	Length    int      `json:"length,omitempty"`
	Reason    string   `json:"reason"`
}

// WildcardReport records the wildcard baseline discovered for a root domain.
type WildcardReport struct {
	Domain        string        `json:"domain"`
	Exists        bool          `json:"exists"`
	CNAMEFlag     string        `json:"cname_flag,omitempty"`
	CNAMEs        []string      `json:"cnames,omitempty"`
	IPs           []string      `json:"ips,omitempty"`
	Samples       []ResolveInfo `json:"samples,omitempty"`
	SampleCount   int           `json:"sample_count"`
	MatchStrategy string        `json:"match_strategy"`
}

// ScanReport is the final scan summary.
type ScanReport struct {
	StartedAt  time.Time        `json:"started_at"`
	FinishedAt time.Time        `json:"finished_at"`
	Results    []Result         `json:"results"`
	Wildcards  []WildcardReport `json:"wildcards"`
	Tested     int              `json:"tested"`
	Filtered   int64            `json:"filtered"`
	Errors     int64            `json:"errors"`
}
