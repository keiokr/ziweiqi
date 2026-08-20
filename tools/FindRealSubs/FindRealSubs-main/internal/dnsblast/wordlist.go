package dnsblast

import (
	"bufio"
	"strings"
)

// ParseWordlist parses a newline/comma/semicolon separated wordlist and returns
// normalized, de-duplicated DNS labels.
func ParseWordlist(content string) []string {
	content = strings.NewReplacer(",", "\n", ";", "\n", "\r", "\n", "\t", "\n", " ", "\n").Replace(content)
	scanner := bufio.NewScanner(strings.NewReader(content))
	seen := make(map[string]struct{})
	var words []string
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if i := strings.Index(line, "#"); i >= 0 {
			line = strings.TrimSpace(line[:i])
		}
		line = strings.Trim(strings.ToLower(line), ".")
		if line == "" || !validLabel(line) {
			continue
		}
		if _, ok := seen[line]; ok {
			continue
		}
		seen[line] = struct{}{}
		words = append(words, line)
	}
	return words
}

func validLabel(label string) bool {
	if len(label) == 0 || len(label) > 63 || label[0] == '-' || label[len(label)-1] == '-' {
		return false
	}
	for _, r := range label {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') || r == '-' {
			continue
		}
		return false
	}
	return true
}
