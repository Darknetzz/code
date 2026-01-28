// gonet — network CLI tools
//
// Usage:
//
//	gonet dns [options] <name|ip>
//	gonet resolve <hostname>
//	gonet whois [options] <domain|ip>
//	gonet ports [options] <host> <port>...
//	gonet ping [options] <host>
//	gonet headers [options] <url>
//	gonet download [options] <url>
//	gonet serve [options] [dir]
//	gonet proxy-headers [options]
//	gonet cert <host:port>
//	gonet urlencode [-d] [string]
//	gonet jwt-decode <token>
//	gonet ip [options]
package main

import (
	"bytes"
	"compress/gzip"
	"crypto/md5"
	"crypto/sha256"
	"crypto/sha512"
	"crypto/tls"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"golang.org/x/net/icmp"
	"golang.org/x/net/ipv4"
	"golang.org/x/net/ipv6"
)

var progName string

func main() {
	progName = filepath.Base(os.Args[0])
	if len(os.Args) < 2 {
		printUsage()
		os.Exit(0)
	}
	cmd := strings.ToLower(os.Args[1])
	args := os.Args[2:]

	var exitCode int
	switch cmd {
	case "dns":
		exitCode = runDNS(args)
	case "resolve":
		exitCode = runResolve(args)
	case "whois":
		exitCode = runWhois(args)
	case "ports":
		exitCode = runPorts(args)
	case "ping":
		exitCode = runPing(args)
	case "headers":
		exitCode = runHeaders(args)
	case "download", "dl":
		exitCode = runDownload(args)
	case "serve":
		exitCode = runServe(args)
	case "proxy-headers":
		exitCode = runProxyHeaders(args)
	case "cert":
		exitCode = runCert(args)
	case "urlencode", "url":
		exitCode = runURLEncode(args)
	case "jwt-decode", "jwt":
		exitCode = runJWTDecode(args)
	case "ip", "myip":
		exitCode = runIP(args)
	case "help", "-h", "--help":
		if len(args) > 0 {
			printCommandHelp(args[0])
		} else {
			printUsage()
		}
		os.Exit(0)
	default:
		fmt.Fprintf(os.Stderr, "%s: unknown command %q\n", progName, cmd)
		printUsage()
		os.Exit(1)
	}
	os.Exit(exitCode)
}

func printUsage() {
	fmt.Fprintf(os.Stderr, "%s — network CLI tools\n\n", progName)
	fmt.Fprintf(os.Stderr, "Usage:\n  %s <command> [options] [args]\n\n", progName)
	fmt.Fprintf(os.Stderr, "Commands:\n")
	fmt.Fprintf(os.Stderr, "  dns          Resolve name or IP (A, AAAA, PTR, MX, TXT)\n")
	fmt.Fprintf(os.Stderr, "  resolve      Resolve hostname to A/AAAA (simple)\n")
	fmt.Fprintf(os.Stderr, "  whois        Whois lookup (domain or IP)\n")
	fmt.Fprintf(os.Stderr, "  ports        Check if TCP ports are open\n")
	fmt.Fprintf(os.Stderr, "  ping         ICMP ping (may need admin on Windows)\n")
	fmt.Fprintf(os.Stderr, "  headers      Fetch URL and print status + headers\n")
	fmt.Fprintf(os.Stderr, "  download     Download URL to file or stdout\n")
	fmt.Fprintf(os.Stderr, "  serve        Static file server\n")
	fmt.Fprintf(os.Stderr, "  proxy-headers  Dump request headers (debug server)\n")
	fmt.Fprintf(os.Stderr, "  cert         Show TLS cert info for host:port\n")
	fmt.Fprintf(os.Stderr, "  urlencode    Encode or decode URL query segment\n")
	fmt.Fprintf(os.Stderr, "  jwt-decode   Decode JWT payload (no verify)\n")
	fmt.Fprintf(os.Stderr, "  ip           Show public and/or local IP addresses\n")
	fmt.Fprintf(os.Stderr, "\n  %s help <command>\n", progName)
}

func printCommandHelp(cmd string) {
	switch strings.ToLower(cmd) {
	case "dns":
		printDNSUsage()
	case "resolve":
		printResolveUsage()
	case "whois":
		printWhoisUsage()
	case "ports":
		printPortsUsage()
	case "ping":
		printPingUsage()
	case "headers":
		printHeadersUsage()
	case "download", "dl":
		printDownloadUsage()
	case "serve":
		printServeUsage()
	case "proxy-headers":
		printProxyHeadersUsage()
	case "cert":
		printCertUsage()
	case "urlencode", "url":
		printURLEncodeUsage()
	case "jwt-decode", "jwt":
		printJWTDecodeUsage()
	case "ip", "myip":
		printIPUsage()
	default:
		fmt.Fprintf(os.Stderr, "%s: unknown command %q\n", progName, cmd)
	}
}

// ---- Shared: HTTP client with timeout and redirects ----
func newHTTPClient(followRedirects bool, timeout time.Duration) *http.Client {
	tr := &http.Transport{
		TLSClientConfig: &tls.Config{InsecureSkipVerify: false},
	}
	client := &http.Client{Transport: tr, Timeout: timeout}
	if !followRedirects {
		client.CheckRedirect = func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }
	}
	return client
}

// ---- DNS ----
func printDNSUsage() {
	fmt.Fprintf(os.Stderr, "Usage: %s dns [options] <name|ip>\n\n", progName)
	fmt.Fprintf(os.Stderr, "  Resolve hostname to IPs or IP to PTR. Optionally MX, TXT.\n\n")
	fmt.Fprintf(os.Stderr, "Options:\n")
	fmt.Fprintf(os.Stderr, "  -mx    Lookup MX records\n")
	fmt.Fprintf(os.Stderr, "  -txt   Lookup TXT records\n")
}

func runDNS(args []string) int {
	fs := flag.NewFlagSet("dns", flag.ExitOnError)
	mx := fs.Bool("mx", false, "Lookup MX")
	txt := fs.Bool("txt", false, "Lookup TXT")
	fs.Usage = func() { printDNSUsage() }
	if err := fs.Parse(args); err != nil {
		return 1
	}
	if fs.NArg() == 0 {
		fmt.Fprintf(os.Stderr, "%s dns: need name or IP\n", progName)
		return 1
	}
	target := strings.TrimSpace(fs.Arg(0))
	if net.ParseIP(target) != nil {
		return runDNSReverse(target)
	}
	// Forward lookup
	ips, err := net.LookupIP(target)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s dns: %v\n", progName, err)
		return 1
	}
	for _, ip := range ips {
		fmt.Println(ip.String())
	}
	if *mx {
		mxs, err := net.LookupMX(target)
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s dns (MX): %v\n", progName, err)
		} else {
			for _, m := range mxs {
				fmt.Printf("MX %d %s\n", m.Pref, m.Host)
			}
		}
	}
	if *txt {
		txts, err := net.LookupTXT(target)
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s dns (TXT): %v\n", progName, err)
		} else {
			for _, t := range txts {
				fmt.Printf("TXT %s\n", t)
			}
		}
	}
	return 0
}

func runDNSReverse(ipStr string) int {
	names, err := net.LookupAddr(ipStr)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s dns: %v\n", progName, err)
		return 1
	}
	for _, n := range names {
		fmt.Println(n)
	}
	return 0
}

// ---- Resolve (simple A/AAAA) ----
func printResolveUsage() {
	fmt.Fprintf(os.Stderr, "Usage: %s resolve <hostname>\n\n", progName)
	fmt.Fprintf(os.Stderr, "  Resolve hostname to A and AAAA addresses.\n")
}

func runResolve(args []string) int {
	if len(args) == 0 {
		fmt.Fprintf(os.Stderr, "%s resolve: need hostname\n", progName)
		return 1
	}
	ips, err := net.LookupIP(args[0])
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s resolve: %v\n", progName, err)
		return 1
	}
	for _, ip := range ips {
		fmt.Println(ip.String())
	}
	return 0
}

// ---- Whois ----
func printWhoisUsage() {
	fmt.Fprintf(os.Stderr, "Usage: %s whois [options] <domain|ip>\n\n", progName)
	fmt.Fprintf(os.Stderr, "Options:\n")
	fmt.Fprintf(os.Stderr, "  -server host  Whois server (default: whois.iana.org)\n")
}

func runWhois(args []string) int {
	fs := flag.NewFlagSet("whois", flag.ExitOnError)
	server := fs.String("server", "whois.iana.org", "Whois server")
	fs.Usage = func() { printWhoisUsage() }
	if err := fs.Parse(args); err != nil {
		return 1
	}
	if fs.NArg() == 0 {
		fmt.Fprintf(os.Stderr, "%s whois: need domain or IP\n", progName)
		return 1
	}
	query := fs.Arg(0)
	addr := net.JoinHostPort(*server, "43")
	conn, err := net.DialTimeout("tcp", addr, 10*time.Second)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s whois: %v\n", progName, err)
		return 1
	}
	defer conn.Close()
	conn.SetDeadline(time.Now().Add(15 * time.Second))
	if _, err := conn.Write([]byte(query + "\r\n")); err != nil {
		fmt.Fprintf(os.Stderr, "%s whois: %v\n", progName, err)
		return 1
	}
	_, err = io.Copy(os.Stdout, conn)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s whois: %v\n", progName, err)
		return 1
	}
	return 0
}

// ---- Ports ----
func printPortsUsage() {
	fmt.Fprintf(os.Stderr, "Usage: %s ports [options] <host> <port>...\n\n", progName)
	fmt.Fprintf(os.Stderr, "  Check if TCP ports are open.\n\n")
	fmt.Fprintf(os.Stderr, "Options:\n")
	fmt.Fprintf(os.Stderr, "  -timeout d  Timeout per port (default 3s)\n")
}

func runPorts(args []string) int {
	fs := flag.NewFlagSet("ports", flag.ExitOnError)
	timeout := fs.Duration("timeout", 3*time.Second, "Timeout per port")
	fs.Usage = func() { printPortsUsage() }
	if err := fs.Parse(args); err != nil {
		return 1
	}
	if fs.NArg() < 2 {
		fmt.Fprintf(os.Stderr, "%s ports: need host and at least one port\n", progName)
		return 1
	}
	host := fs.Arg(0)
	ports := fs.Args()[1:]
	anyFailed := false
	for _, p := range ports {
		addr := net.JoinHostPort(host, p)
		start := time.Now()
		conn, err := net.DialTimeout("tcp", addr, *timeout)
		elapsed := time.Since(start)
		if err != nil {
			fmt.Printf("%s: closed/filtered (%v)\n", addr, err)
			anyFailed = true
			continue
		}
		conn.Close()
		fmt.Printf("%s: open (%.2f ms)\n", addr, float64(elapsed.Microseconds())/1000)
	}
	if anyFailed {
		return 1
	}
	return 0
}

// ---- Ping (ICMP) ----
func printPingUsage() {
	fmt.Fprintf(os.Stderr, "Usage: %s ping [options] <host>\n\n", progName)
	fmt.Fprintf(os.Stderr, "  ICMP ping. May require admin/root for raw sockets.\n\n")
	fmt.Fprintf(os.Stderr, "Options:\n")
	fmt.Fprintf(os.Stderr, "  -c n   Count (default 4)\n")
	fmt.Fprintf(os.Stderr, "  -6     Use IPv6\n")
}

func runPing(args []string) int {
	fs := flag.NewFlagSet("ping", flag.ExitOnError)
	count := fs.Int("c", 4, "Count")
	useIPv6 := fs.Bool("6", false, "IPv6")
	fs.Usage = func() { printPingUsage() }
	if err := fs.Parse(args); err != nil {
		return 1
	}
	if fs.NArg() == 0 {
		fmt.Fprintf(os.Stderr, "%s ping: need host\n", progName)
		return 1
	}
	host := fs.Arg(0)
	ips, err := net.LookupIP(host)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s ping: %v\n", progName, err)
		return 1
	}
	var ip net.IP
	for _, i := range ips {
		if *useIPv6 && i.To16() != nil && i.To4() == nil {
			ip = i
			break
		}
		if !*useIPv6 && i.To4() != nil {
			ip = i
			break
		}
	}
	if ip == nil {
		if *useIPv6 {
			fmt.Fprintf(os.Stderr, "%s ping: no IPv6 address for %s\n", progName, host)
		} else {
			fmt.Fprintf(os.Stderr, "%s ping: no IPv4 address for %s\n", progName, host)
		}
		return 1
	}

	proto := "ip4:icmp"
	if ip.To4() == nil {
		proto = "ip6:ipv6-icmp"
	}
	conn, err := icmp.ListenPacket(proto, "0.0.0.0")
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s ping: %v (try running as admin on Windows)\n", progName, err)
		return 1
	}
	defer conn.Close()

	fmt.Printf("PING %s (%s)\n", host, ip)
	var rtts []time.Duration
	for seq := 0; seq < *count; seq++ {
		var wb []byte
		if ip.To4() != nil {
			msg := &icmp.Message{
				Type: ipv4.ICMPTypeEcho, Code: 0,
				Body: &icmp.Echo{ID: os.Getpid() & 0xffff, Seq: seq + 1, Data: []byte("gonet-ping")},
			}
			wb, err = msg.Marshal(nil)
		} else {
			msg := &icmp.Message{
				Type: ipv6.ICMPTypeEchoRequest, Code: 0,
				Body: &icmp.Echo{ID: os.Getpid() & 0xffff, Seq: seq + 1, Data: []byte("gonet-ping")},
			}
			wb, err = msg.Marshal(nil)
		}
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s ping: %v\n", progName, err)
			return 1
		}
		dest := &net.IPAddr{IP: ip}
		start := time.Now()
		if _, err := conn.WriteTo(wb, dest); err != nil {
			fmt.Fprintf(os.Stderr, "%s ping: %v\n", progName, err)
			return 1
		}
		conn.SetReadDeadline(time.Now().Add(5 * time.Second))
		rb := make([]byte, 1500)
		n, _, err := conn.ReadFrom(rb)
		rtt := time.Since(start)
		if err != nil {
			fmt.Printf("Request timeout for seq %d\n", seq+1)
			continue
		}
		var protoNum int
		if ip.To4() != nil {
			protoNum = 1
		} else {
			protoNum = 58
		}
		rm, err := icmp.ParseMessage(protoNum, rb[:n])
		if err != nil {
			fmt.Printf("Reply (parse err): %v\n", err)
			continue
		}
		switch rm.Type {
		case ipv4.ICMPTypeEchoReply, ipv6.ICMPTypeEchoReply:
			rtts = append(rtts, rtt)
			fmt.Printf("%d bytes from %s: seq=%d time=%.2f ms\n", n, ip, seq+1, float64(rtt.Microseconds())/1000)
		default:
			fmt.Printf("Unexpected reply type %v\n", rm.Type)
		}
	}
	if len(rtts) > 0 {
		var min, max, sum time.Duration
		min, max = rtts[0], rtts[0]
		for _, r := range rtts {
			if r < min {
				min = r
			}
			if r > max {
				max = r
			}
			sum += r
		}
		avg := time.Duration(int64(sum) / int64(len(rtts)))
		fmt.Printf("--- %s ping statistics ---\n", host)
		fmt.Printf("%d packets transmitted, %d received, %.0f%% packet loss\n", *count, len(rtts), 100*(1-float64(len(rtts))/float64(*count)))
		fmt.Printf("rtt min/avg/max = %.2f/%.2f/%.2f ms\n", float64(min.Microseconds())/1000, float64(avg.Microseconds())/1000, float64(max.Microseconds())/1000)
	}
	return 0
}

// ---- Headers ----
func printHeadersUsage() {
	fmt.Fprintf(os.Stderr, "Usage: %s headers [options] <url>\n\n", progName)
	fmt.Fprintf(os.Stderr, "  Fetch URL and print status and response headers (optional body).\n\n")
	fmt.Fprintf(os.Stderr, "Options:\n")
	fmt.Fprintf(os.Stderr, "  -L         Follow redirects (default)\n")
	fmt.Fprintf(os.Stderr, "  -no-follow Do not follow redirects\n")
	fmt.Fprintf(os.Stderr, "  -body      Print response body to stdout\n")
	fmt.Fprintf(os.Stderr, "  -H header  Add header (key: value)\n")
	fmt.Fprintf(os.Stderr, "  -X method  Request method (default GET)\n")
}

func runHeaders(args []string) int {
	fs := flag.NewFlagSet("headers", flag.ExitOnError)
	follow := fs.Bool("L", true, "Follow redirects")
	noFollow := fs.Bool("no-follow", false, "Do not follow redirects")
	body := fs.Bool("body", false, "Print body")
	method := fs.String("X", "GET", "Method")
	fs.Usage = func() { printHeadersUsage() }
	var addHeaders []string
	fs.Func("H", "Header key: value", func(s string) error {
		addHeaders = append(addHeaders, s)
		return nil
	})
	if err := fs.Parse(args); err != nil {
		return 1
	}
	if fs.NArg() == 0 {
		fmt.Fprintf(os.Stderr, "%s headers: need URL\n", progName)
		return 1
	}
	rawURL := fs.Arg(0)
	req, err := http.NewRequest(*method, rawURL, nil)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s headers: %v\n", progName, err)
		return 1
	}
	for _, h := range addHeaders {
		if idx := strings.Index(h, ":"); idx > 0 {
			req.Header.Set(strings.TrimSpace(h[:idx]), strings.TrimSpace(h[idx+1:]))
		}
	}
	doFollow := *follow && !*noFollow
	client := newHTTPClient(doFollow, 30*time.Second)
	resp, err := client.Do(req)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s headers: %v\n", progName, err)
		return 1
	}
	defer resp.Body.Close()
	fmt.Printf("%s %s\n", resp.Proto, resp.Status)
	for k, v := range resp.Header {
		for _, vv := range v {
			fmt.Printf("%s: %s\n", k, vv)
		}
	}
	fmt.Println()
	if *body {
		var out io.Writer = os.Stdout
		if strings.EqualFold(resp.Header.Get("Content-Encoding"), "gzip") {
			gr, err := gzip.NewReader(resp.Body)
			if err != nil {
				fmt.Fprintf(os.Stderr, "%s headers: %v\n", progName, err)
				return 1
			}
			defer gr.Close()
			io.Copy(out, gr)
		} else {
			io.Copy(out, resp.Body)
		}
	}
	return 0
}

// ---- Download ----
func printDownloadUsage() {
	fmt.Fprintf(os.Stderr, "Usage: %s download [options] <url>\n\n", progName)
	fmt.Fprintf(os.Stderr, "  Download URL to file or stdout.\n\n")
	fmt.Fprintf(os.Stderr, "Options:\n")
	fmt.Fprintf(os.Stderr, "  -o path   Output file (default: stdout)\n")
	fmt.Fprintf(os.Stderr, "  -hash algo  Print hash (md5, sha256, sha512) of body\n")
}

func runDownload(args []string) int {
	fs := flag.NewFlagSet("download", flag.ExitOnError)
	output := fs.String("o", "", "Output file")
	hashAlgo := fs.String("hash", "", "Print hash (md5, sha256, sha512)")
	fs.Usage = func() { printDownloadUsage() }
	if err := fs.Parse(args); err != nil {
		return 1
	}
	if fs.NArg() == 0 {
		fmt.Fprintf(os.Stderr, "%s download: need URL\n", progName)
		return 1
	}
	rawURL := fs.Arg(0)
	client := newHTTPClient(true, 0)
	resp, err := client.Get(rawURL)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s download: %v\n", progName, err)
		return 1
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		fmt.Fprintf(os.Stderr, "%s download: %s\n", progName, resp.Status)
		return 1
	}
	var dest io.Writer
	if *output == "" {
		dest = os.Stdout
	} else {
		f, err := os.Create(*output)
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s download: %v\n", progName, err)
			return 1
		}
		defer f.Close()
		dest = f
	}
	var r io.Reader = resp.Body
	if *hashAlgo != "" {
		h := newHasher(*hashAlgo)
		if h == nil {
			fmt.Fprintf(os.Stderr, "%s download: unknown hash %q\n", progName, *hashAlgo)
			return 1
		}
		r = io.TeeReader(resp.Body, h)
		_, err = io.Copy(dest, r)
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s download: %v\n", progName, err)
			return 1
		}
		if summer, ok := h.(interface{ Sum(b []byte) []byte }); ok {
			outName := *output
			if outName == "" {
				outName = "-"
			}
			fmt.Fprintf(os.Stderr, "%s  %s\n", hashSumHex(summer), outName)
		}
		return 0
	}
	_, err = io.Copy(dest, r)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s download: %v\n", progName, err)
		return 1
	}
	return 0
}

func newHasher(algo string) io.Writer {
	switch strings.ToLower(algo) {
	case "md5":
		return md5.New()
	case "sha256":
		return sha256.New()
	case "sha512":
		return sha512.New()
	default:
		return nil
	}
}

func hashSumHex(h interface{ Sum(b []byte) []byte }) string {
	return hex.EncodeToString(h.Sum(nil))
}

// ---- Serve ----
func printServeUsage() {
	fmt.Fprintf(os.Stderr, "Usage: %s serve [options] [dir]\n\n", progName)
	fmt.Fprintf(os.Stderr, "  Static file server. dir defaults to current directory.\n\n")
	fmt.Fprintf(os.Stderr, "Options:\n")
	fmt.Fprintf(os.Stderr, "  -port p   Port (default 8080)\n")
	fmt.Fprintf(os.Stderr, "  -bind a   Bind address (default 0.0.0.0)\n")
}

func runServe(args []string) int {
	fs := flag.NewFlagSet("serve", flag.ExitOnError)
	port := fs.String("port", "8080", "Port")
	bind := fs.String("bind", "0.0.0.0", "Bind address")
	fs.Usage = func() { printServeUsage() }
	if err := fs.Parse(args); err != nil {
		return 1
	}
	dir := "."
	if fs.NArg() > 0 {
		dir = fs.Arg(0)
	}
	dir, err := filepath.Abs(dir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s serve: %v\n", progName, err)
		return 1
	}
	if _, err := os.Stat(dir); err != nil {
		fmt.Fprintf(os.Stderr, "%s serve: %v\n", progName, err)
		return 1
	}
	addr := net.JoinHostPort(*bind, *port)
	fmt.Fprintf(os.Stderr, "Serving %s at http://%s\n", dir, addr)
	handler := http.FileServer(http.Dir(dir))
	if err := http.ListenAndServe(addr, handler); err != nil {
		fmt.Fprintf(os.Stderr, "%s serve: %v\n", progName, err)
		return 1
	}
	return 0
}

// ---- Proxy-headers ----
func printProxyHeadersUsage() {
	fmt.Fprintf(os.Stderr, "Usage: %s proxy-headers [options]\n\n", progName)
	fmt.Fprintf(os.Stderr, "  HTTP server that dumps request method, URL, and headers.\n\n")
	fmt.Fprintf(os.Stderr, "Options:\n")
	fmt.Fprintf(os.Stderr, "  -port p   Port (default 8080)\n")
	fmt.Fprintf(os.Stderr, "  -bind a   Bind address (default 127.0.0.1)\n")
}

func runProxyHeaders(args []string) int {
	fs := flag.NewFlagSet("proxy-headers", flag.ExitOnError)
	port := fs.String("port", "8080", "Port")
	bind := fs.String("bind", "127.0.0.1", "Bind address")
	fs.Usage = func() { printProxyHeadersUsage() }
	if err := fs.Parse(args); err != nil {
		return 1
	}
	addr := net.JoinHostPort(*bind, *port)
	handler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var buf strings.Builder
		buf.WriteString(r.Method)
		buf.WriteString(" ")
		buf.WriteString(r.URL.RequestURI())
		buf.WriteString("\n\n")
		for k, v := range r.Header {
			for _, vv := range v {
				buf.WriteString(k)
				buf.WriteString(": ")
				buf.WriteString(vv)
				buf.WriteString("\n")
			}
		}
		if r.Body != nil {
			body, _ := io.ReadAll(r.Body)
			if len(body) > 0 {
				buf.WriteString("\nBody:\n")
				buf.Write(body)
			}
		}
		fmt.Println(buf.String())
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("OK\n"))
	})
	fmt.Fprintf(os.Stderr, "Dumping requests at http://%s\n", addr)
	if err := http.ListenAndServe(addr, handler); err != nil {
		fmt.Fprintf(os.Stderr, "%s proxy-headers: %v\n", progName, err)
		return 1
	}
	return 0
}

// ---- Cert ----
func printCertUsage() {
	fmt.Fprintf(os.Stderr, "Usage: %s cert <host:port>\n\n", progName)
	fmt.Fprintf(os.Stderr, "  Show TLS certificate info (subject, issuer, expiry, SANs).\n")
}

func runCert(args []string) int {
	if len(args) == 0 {
		fmt.Fprintf(os.Stderr, "%s cert: need host:port\n", progName)
		return 1
	}
	addr := args[0]
	if !strings.Contains(addr, ":") {
		addr = net.JoinHostPort(addr, "443")
	}
	conn, err := tls.Dial("tcp", addr, &tls.Config{InsecureSkipVerify: true})
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s cert: %v\n", progName, err)
		return 1
	}
	defer conn.Close()
	st := conn.ConnectionState()
	if len(st.PeerCertificates) == 0 {
		fmt.Fprintf(os.Stderr, "%s cert: no peer certificates\n", progName)
		return 1
	}
	cert := st.PeerCertificates[0]
	fmt.Printf("Subject:   %s\n", cert.Subject)
	fmt.Printf("Issuer:    %s\n", cert.Issuer)
	fmt.Printf("NotBefore: %s\n", cert.NotBefore)
	fmt.Printf("NotAfter:  %s\n", cert.NotAfter)
	fmt.Printf("DNS names: %s\n", strings.Join(cert.DNSNames, ", "))
	return 0
}

// ---- URL encode/decode ----
func printURLEncodeUsage() {
	fmt.Fprintf(os.Stderr, "Usage: %s urlencode [-d] [string]\n\n", progName)
	fmt.Fprintf(os.Stderr, "  Encode (default) or decode URL query segment. Reads stdin if no string.\n\n")
	fmt.Fprintf(os.Stderr, "Options:\n")
	fmt.Fprintf(os.Stderr, "  -d   Decode instead of encode\n")
}

func runURLEncode(args []string) int {
	fs := flag.NewFlagSet("urlencode", flag.ExitOnError)
	decode := fs.Bool("d", false, "Decode")
	fs.Usage = func() { printURLEncodeUsage() }
	if err := fs.Parse(args); err != nil {
		return 1
	}
	input := strings.TrimSpace(strings.Join(fs.Args(), " "))
	if input == "" {
		bs, err := io.ReadAll(os.Stdin)
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s urlencode: %v\n", progName, err)
			return 1
		}
		input = string(bs)
	}
	if *decode {
		out, err := url.QueryUnescape(input)
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s urlencode: %v\n", progName, err)
			return 1
		}
		fmt.Print(out)
	} else {
		fmt.Print(url.QueryEscape(input))
	}
	return 0
}

// ---- JWT decode ----
func printJWTDecodeUsage() {
	fmt.Fprintf(os.Stderr, "Usage: %s jwt-decode <token>\n\n", progName)
	fmt.Fprintf(os.Stderr, "  Decode JWT payload (no signature verification). Token can be full JWT or just payload.\n")
}

func runJWTDecode(args []string) int {
	if len(args) == 0 {
		fmt.Fprintf(os.Stderr, "%s jwt-decode: need token\n", progName)
		return 1
	}
	token := strings.TrimSpace(args[0])
	parts := strings.Split(token, ".")
	var payload string
	if len(parts) == 3 {
		payload = parts[1]
	} else if len(parts) == 1 {
		payload = parts[0]
	} else {
		fmt.Fprintf(os.Stderr, "%s jwt-decode: expected 3 parts or single payload, got %d\n", progName, len(parts))
		return 1
	}
	// JWT base64 is raw URL encoding, with optional padding
	decoded, err := base64.RawURLEncoding.DecodeString(payload)
	if err != nil {
		decoded, err = base64.URLEncoding.DecodeString(payload)
	}
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s jwt-decode: %v\n", progName, err)
		return 1
	}
	var out bytes.Buffer
	if err := json.Indent(&out, decoded, "", "  "); err != nil {
		fmt.Print(string(decoded))
		return 0
	}
	fmt.Println(out.String())
	return 0
}

// ---- IP (public / local) ----
var ipifyURLs = []string{"https://api.ipify.org", "https://icanhazip.com"}

func printIPUsage() {
	fmt.Fprintf(os.Stderr, "Usage: %s ip [options]\n\n", progName)
	fmt.Fprintf(os.Stderr, "  Show public (external) and/or local (internal) IP addresses.\n\n")
	fmt.Fprintf(os.Stderr, "Options:\n")
	fmt.Fprintf(os.Stderr, "  -public    Only show public IP\n")
	fmt.Fprintf(os.Stderr, "  -internal  Only show local interface IPs\n")
}

func runIP(args []string) int {
	fs := flag.NewFlagSet("ip", flag.ExitOnError)
	publicOnly := fs.Bool("public", false, "Only public IP")
	internalOnly := fs.Bool("internal", false, "Only local IPs")
	fs.Usage = func() { printIPUsage() }
	if err := fs.Parse(args); err != nil {
		return 1
	}
	showPublic := *publicOnly || (!*publicOnly && !*internalOnly)
	showInternal := *internalOnly || (!*publicOnly && !*internalOnly)

	anyErr := false
	if showPublic {
		pub, err := getPublicIP()
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s ip: public: %v\n", progName, err)
			anyErr = true
		} else {
			fmt.Printf("Public:   %s\n", pub)
		}
	}
	if showInternal {
		ips := getLocalIPs()
		if len(ips) == 0 {
			fmt.Fprintf(os.Stderr, "%s ip: no local IPs found\n", progName)
			anyErr = true
		} else {
			for _, ip := range ips {
				fmt.Printf("Internal: %s\n", ip)
			}
		}
	}
	if anyErr {
		return 1
	}
	return 0
}

func getPublicIP() (string, error) {
	client := newHTTPClient(true, 10*time.Second)
	for _, u := range ipifyURLs {
		resp, err := client.Get(u)
		if err != nil {
			continue
		}
		if resp.StatusCode != http.StatusOK {
			resp.Body.Close()
			continue
		}
		b, err := io.ReadAll(resp.Body)
		resp.Body.Close()
		if err != nil {
			continue
		}
		ip := strings.TrimSpace(string(b))
		if net.ParseIP(ip) != nil {
			return ip, nil
		}
	}
	return "", fmt.Errorf("could not get public IP from any service")
}

func getLocalIPs() []string {
	seen := make(map[string]struct{})
	ifaces, err := net.Interfaces()
	if err != nil {
		return nil
	}
	for _, iface := range ifaces {
		if iface.Flags&net.FlagUp == 0 {
			continue
		}
		addrs, err := iface.Addrs()
		if err != nil {
			continue
		}
		for _, a := range addrs {
			ipNet, ok := a.(*net.IPNet)
			if !ok {
				continue
			}
			ip := ipNet.IP
			if ip == nil || ip.IsLoopback() {
				continue
			}
			ip = ip.To4()
			if ip == nil {
				continue
			}
			s := ip.String()
			if _, ok := seen[s]; ok {
				continue
			}
			seen[s] = struct{}{}
		}
	}
	out := make([]string, 0, len(seen))
	for s := range seen {
		out = append(out, s)
	}
	sort.Strings(out)
	return out
}
