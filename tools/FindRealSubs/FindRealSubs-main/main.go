package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/wintrysec/FindSubs/internal/dnsblast"
)

func main() {
	var domain, domfile, wordlistFile, dnsServers, outFile string
	var concurrency, timeoutSeconds, retries, wildcardSamples int
	var jsonOut, showFiltered bool

	flag.Usage = usage
	flag.StringVar(&domain, "d", "", "\u76ee\u6807\u6839\u57df\u540d")
	flag.StringVar(&domain, "domain", "", "\u540c -d")
	flag.StringVar(&domfile, "df", "", "\u76ee\u6807\u57df\u540d\u6587\u4ef6")
	flag.StringVar(&domfile, "domfile", "", "\u540c -df")
	flag.StringVar(&wordlistFile, "w", "", "\u5b50\u57df\u540d\u5b57\u5178\u6587\u4ef6\uff0c\u5fc5\u586b")
	flag.StringVar(&wordlistFile, "wordlist", "", "\u540c -w")
	flag.StringVar(&dnsServers, "dns", "223.5.5.5,119.29.29.29,8.8.8.8,1.1.1.1", "DNS\u670d\u52a1\u5668")
	flag.IntVar(&concurrency, "c", 60, "\u5e76\u53d1\u6570")
	flag.IntVar(&timeoutSeconds, "t", 3, "\u8d85\u65f6\u79d2\u6570")
	flag.IntVar(&timeoutSeconds, "timeout", 3, "\u540c -t")
	flag.IntVar(&retries, "r", 1, "DNS\u91cd\u8bd5\u6b21\u6570")
	flag.IntVar(&retries, "retries", 1, "\u540c -r")
	flag.IntVar(&wildcardSamples, "m", 5, "\u6cdb\u89e3\u6790\u6837\u672c\u6570")
	flag.IntVar(&wildcardSamples, "samples", 5, "\u540c -m")
	flag.StringVar(&outFile, "o", "", "\u7ed3\u679c\u8f93\u51fa\u6587\u4ef6")
	flag.BoolVar(&jsonOut, "j", false, "\u8f93\u51faJSON\u62a5\u544a")
	flag.BoolVar(&jsonOut, "json", false, "\u540c -j")
	flag.BoolVar(&showFiltered, "sf", false, "\u663e\u793a\u8fc7\u6ee4\u65e5\u5fd7")
	flag.BoolVar(&showFiltered, "show-filtered", false, "\u540c -sf")
	flag.Parse()

	domains := splitItems(domain)
	if domfile != "" {
		items, err := readItemsFile(domfile)
		if err != nil {
			fatal(err)
		}
		domains = append(domains, items...)
	}
	if len(domains) == 0 {
		fatal(fmt.Errorf("\u8bf7\u4f7f\u7528 -d \u6307\u5b9a\u76ee\u6807\u57df\u540d\uff0c\u6216\u4f7f\u7528 -df \u6307\u5b9a\u76ee\u6807\u6587\u4ef6"))
	}
	if wordlistFile == "" {
		fatal(fmt.Errorf("\u8bf7\u4f7f\u7528 -w \u6307\u5b9a\u5b50\u57df\u540d\u5b57\u5178\u6587\u4ef6"))
	}
	wordlistPath, err := resolveWordlistPath(wordlistFile)
	if err != nil {
		fatal(err)
	}
	data, err := os.ReadFile(wordlistPath)
	if err != nil {
		fatal(err)
	}
	words := dnsblast.ParseWordlist(string(data))
	if len(words) == 0 {
		fatal(fmt.Errorf("\u5b57\u5178\u4e3a\u7a7a: %s", wordlistPath))
	}
	if outFile == "" {
		outFile = filepath.Join("results", fmt.Sprintf("findrealsubs_%s.txt", time.Now().Format("20060102_150405")))
	}

	opts := dnsblast.Options{
		Domains:          domains,
		Wordlist:         words,
		DNSServers:       splitItems(dnsServers),
		Concurrency:      concurrency,
		Timeout:          time.Duration(timeoutSeconds) * time.Second,
		Retries:          retries,
		WildcardSamples:  wildcardSamples,
		ShowFiltered:     showFiltered,
		HTTPVerify:       true,
		FastWildcardHTTP: true,
	}
	progress := newProgressPrinter()
	if !jsonOut {
		opts.OnEvent = func(e dnsblast.Event) {
			switch e.Type {
			case "progress":
				progress.Update(e.Domain, e.Done, e.Total)
			case "found":
				progress.Found(e.Message)
			case "filtered":
				if showFiltered {
					progress.Log(e.Message)
				}
			case "log", "done":
				progress.Log(e.Message)
			}
		}
	}

	report, err := dnsblast.Run(context.Background(), opts)
	if err != nil {
		fatal(err)
	}
	if !jsonOut {
		progress.Finish()
	}
	if jsonOut {
		enc := json.NewEncoder(os.Stdout)
		enc.SetIndent("", "  ")
		_ = enc.Encode(report)
	} else {
		fmt.Printf("\n=================== \u5171\u53d1\u73b0 %d \u4e2a\u5b50\u57df\u540d ===================\n", len(report.Results))
		for i := range report.Results {
			fmt.Println(formatResultLine(&report.Results[i]))
		}
	}
	if err := saveResults(outFile, report.Results); err != nil {
		fatal(err)
	}
	fmt.Printf("\n\u7ed3\u679c\u5df2\u4fdd\u5b58: %s\n", outFile)
}

func usage() {
	fmt.Fprint(os.Stderr,
		"FindRealSubs \u6cdb\u89e3\u6790\u5b50\u57df\u540d\u7206\u7834\u547d\u4ee4\u884c\u7248\n\n"+
			"\u793a\u4f8b:\n"+
			"  FindRealSubs.exe -d   baidu.com  -w subdomains.txt -c 60 -t 3 -m 5\n"+
			"  FindRealSubs.exe -df domains.txt -w subdomains.txt \n\n"+
			"\u8f93\u51fa\u683c\u5f0f:\n"+
			"  \u53d1\u73b0\uff1ahttp\u6216https\u5b50\u57df\u540d\u5730\u5740\uff0c\u6807\u9898\uff1axxx\uff1b\u957f\u5ea6\uff1axxx\uff1b\u72b6\u6001\u7801=200\n\n"+
			"\u5fc5\u586b\u53c2\u6570:\n"+
			"  -d,  -domain        \u76ee\u6807\u6839\u57df\u540d\uff0c\u591a\u4e2a\u53ef\u7528\u9017\u53f7/\u7a7a\u683c/\u6362\u884c\u5206\u9694\n"+
			"  -df, -domfile       \u76ee\u6807\u57df\u540d\u6587\u4ef6\uff0c\u4e00\u884c\u4e00\u4e2a\uff1b\u53ef\u66ff\u4ee3 -d\n"+
			"  -w,  -wordlist      \u5b50\u57df\u540d\u5b57\u5178\u6587\u4ef6\uff0c\u5fc5\u586b\n\n"+
			"\u5176\u4ed6\u53c2\u6570:\n"+
			"  -c                  \u5e76\u53d1\u6570\uff0c\u9ed8\u8ba4 60\n"+
			"  -t,  -timeout         HTTP/DNS \u8d85\u65f6\u65f6\u95f4\uff0c\u5355\u4f4d\u79d2\uff0c\u9ed8\u8ba4 3\n"+
			"  -r,  -retries           DNS \u91cd\u8bd5\u6b21\u6570\uff0c\u9ed8\u8ba4 1\n"+
			"  -dns                     DNS \u670d\u52a1\u5668\uff0c\u9017\u53f7\u5206\u9694\n"+
			"  -m,  -samples       \u6cdb\u89e3\u6790\u968f\u673a\u6837\u672c\u6570\u91cf\uff0c\u9ed8\u8ba4 5\n"+
			"  -o                         \u9ed8\u8ba4\u8f93\u51fa\u7ed3\u679c\u6587\u4ef6\uff0c results/findrealsubs_\u65f6\u95f4.txt\n")
}

type progressPrinter struct {
	started time.Time
	last    time.Time
	lastLen int
	found   int
}

func newProgressPrinter() *progressPrinter { return &progressPrinter{started: time.Now()} }

func (p *progressPrinter) Update(domain string, done, total int) {
	if total <= 0 {
		return
	}
	now := time.Now()
	if done < total && now.Sub(p.last) < 180*time.Millisecond {
		return
	}
	p.last = now
	elapsed := now.Sub(p.started)
	if elapsed <= 0 {
		elapsed = time.Second
	}
	rate := float64(done) / elapsed.Seconds()
	eta := "--"
	if rate > 0 && done < total {
		eta = formatDuration(time.Duration(float64(total-done)/rate) * time.Second)
	}
	percent := float64(done) * 100 / float64(total)
	bar := progressBar(percent, 24)
	line := fmt.Sprintf("\r\u8fdb\u5ea6 %s %d/%d %.1f%% \u901f\u5ea6 %.1f/s ETA %s \u53d1\u73b0 %d \u5f53\u524d %s", bar, done, total, percent, rate, eta, p.found, domain)
	p.printInline(line)
}

func (p *progressPrinter) Found(msg string) {
	p.found++
	p.clearInline()
	fmt.Println(msg)
}

func (p *progressPrinter) Log(msg string) {
	p.clearInline()
	fmt.Println(msg)
}

func (p *progressPrinter) Finish() { p.clearInline() }

func (p *progressPrinter) printInline(line string) {
	pad := ""
	if p.lastLen > len([]rune(line)) {
		pad = strings.Repeat(" ", p.lastLen-len([]rune(line)))
	}
	fmt.Print(line + pad)
	p.lastLen = len([]rune(line))
}

func (p *progressPrinter) clearInline() {
	if p.lastLen > 0 {
		fmt.Print("\r" + strings.Repeat(" ", p.lastLen) + "\r")
		p.lastLen = 0
	}
}

func progressBar(percent float64, width int) string {
	if percent < 0 {
		percent = 0
	}
	if percent > 100 {
		percent = 100
	}
	filled := int(percent / 100 * float64(width))
	if filled > width {
		filled = width
	}
	return "[" + strings.Repeat("=", filled) + strings.Repeat(".", width-filled) + "]"
}

func formatDuration(d time.Duration) string {
	if d < 0 {
		d = 0
	}
	d = d.Round(time.Second)
	m := int(d.Minutes())
	s := int(d.Seconds()) % 60
	if m >= 60 {
		h := m / 60
		m = m % 60
		return fmt.Sprintf("%dh%02dm%02ds", h, m, s)
	}
	return fmt.Sprintf("%dm%02ds", m, s)
}

func formatResultLine(r *dnsblast.Result) string {
	if r == nil {
		return ""
	}
	url := r.URL
	if url == "" {
		url = r.Subdomain
	}
	title := strings.TrimSpace(r.Title)
	if title == "" {
		title = "-"
	}
	return fmt.Sprintf("\u53d1\u73b0\uff1a%s\uff0c\u6807\u9898\uff1a%s\uff1b\u957f\u5ea6\uff1a%d\uff1b\u72b6\u6001\u7801=%d", url, title, r.Length, r.Status)
}

func resolveWordlistPath(input string) (string, error) {
	name := strings.TrimSpace(input)
	if name == "" {
		return "", fmt.Errorf("\u8bf7\u4f7f\u7528 -w \u6307\u5b9a\u5b50\u57df\u540d\u5b57\u5178\u6587\u4ef6")
	}
	if filepath.IsAbs(name) || filepath.Dir(name) != "." {
		return name, nil
	}
	path := filepath.Join("wordlists", name)
	if _, err := os.Stat(path); err != nil {
		return "", fmt.Errorf("\u5b57\u5178\u4e0d\u5b58\u5728: %s\uff08-w \u53ea\u4ece wordlists \u5b50\u6587\u4ef6\u5939\u67e5\u627e\uff09", path)
	}
	return path, nil
}

func splitItems(s string) []string {
	var out []string
	for _, p := range strings.FieldsFunc(s, func(r rune) bool { return r == ',' || r == ';' || r == '\n' || r == '\r' || r == '\t' || r == ' ' }) {
		p = strings.TrimSpace(p)
		if p != "" {
			out = append(out, p)
		}
	}
	return out
}

func readItemsFile(path string) ([]string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	return splitItems(string(data)), nil
}

func saveResults(path string, results []dnsblast.Result) error {
	if path == "" {
		return nil
	}
	dir := filepath.Dir(path)
	if dir != "." {
		if err := os.MkdirAll(dir, 0755); err != nil {
			return err
		}
	}
	var b strings.Builder
	for i := range results {
		b.WriteString(formatResultLine(&results[i]))
		b.WriteString("\n")
	}
	return os.WriteFile(path, []byte(b.String()), 0644)
}

func fatal(err error) {
	fmt.Fprintln(os.Stderr, "\u9519\u8bef:", err)
	os.Exit(1)
}
