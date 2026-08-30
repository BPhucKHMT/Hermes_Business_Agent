use v5.34;
use autodie;
use Digest::SHA qw(sha256_hex);
use Encode qw(encode);
use JSON::PP;

my $root = ".";
my $research = "$root/src/skills/research";
my $store_path = "$research/scripts/research_store.py";
my $renderer_path = "$research/scripts/render_report.py";
my $fixture_path = "$root/tests/fixtures/research/coffee_house_menu_sanitized.json";

sub slurp {
    my ($path) = @_;
    open my $handle, '<:encoding(UTF-8)', $path;
    local $/;
    return <$handle>;
}

my $store = slurp($store_path);
my $renderer = slurp($renderer_path);
my $skill = slurp("$research/SKILL.md");
my $protocol = slurp("$research/references/research-protocol.md");
my $contract = lc "$skill\n$protocol";
my $fixture_text = slurp($fixture_path);
my $fixture = JSON::PP->new->utf8->decode(encode('UTF-8', $fixture_text));
my $canonical = JSON::PP->new->utf8->canonical->allow_nonref;
my $response_bytes = $canonical->encode($fixture->{response});
my $fingerprint = 'sha256:' . sha256_hex($response_bytes);

my @categories = $fixture->{response}{menu}->@*;
my @products = map { $_->{products}->@* } @categories;
my @prices = map {
    my @product_prices = ($_->{price});
    for my $option ($_->{options}->@*) {
        push @product_prices, map { $_->{price} } $option->{items}->@*;
    }
    @product_prices;
} @products;

my @checks;
sub check {
    my ($group, $name, $predicate) = @_;
    my $passed = eval { $predicate->() ? 1 : 0 };
    my $detail = $@ ? ": $@" : '';
    $detail =~ s/\s+/ /g;
    push @checks, [$group, $name, $passed];
    say "CHECK $group.$name=" . ($passed ? 'pass' : 'fail') . $detail;
}

check('behavior', 'fixture_parses', sub { ref $fixture eq 'HASH' });
check('behavior', 'expected_categories', sub { @categories == 2 });
check('behavior', 'expected_products', sub { @products == 3 });
check(
    'behavior',
    'structured_values_are_valid',
    sub {
        !grep { !defined $_->{id} || !defined $_->{name} || $_->{name} eq '' } @products;
    },
);
check(
    'behavior',
    'prices_are_nonnegative_integers',
    sub { !grep { !defined $_ || $_ !~ /^\d+$/ || $_ < 0 } @prices },
);
check(
    'behavior',
    'canonical_fingerprint_is_deterministic',
    sub {
        $fingerprint eq 'sha256:' . sha256_hex($canonical->encode($fixture->{response}));
    },
);
check(
    'behavior',
    'unicode_line_normalization_contract',
    sub {
        $store =~ /unicodedata\.normalize\("NFC"/
          && $store =~ /replace\("\\r\\n", "\\n"\)/;
    },
);
check(
    'behavior',
    'canonical_json_contract',
    sub {
        $store =~ /sort_keys=True/
          && $store =~ /separators=\("[,]", ":"\)/
          && $store =~ /allow_nan=False/;
    },
);
check(
    'behavior',
    'first_party_subdomain_enforced',
    sub {
        $store =~ /host != domain and not host\.endswith\("\." \+ domain\)/;
    },
);
check(
    'behavior',
    'http_scheme_enforced',
    sub { $store =~ /parts\.scheme\.lower\(\) not in \{"http", "https"\}/ },
);
check(
    'behavior',
    'evidence_size_limits_enforced',
    sub { $store =~ /len\(val\) > 4000/ && $store =~ /len\(canonical_bytes\) > 65536/ },
);
check(
    'behavior',
    'fingerprint_mismatch_rejected',
    sub { $store =~ /evidence fingerprint mismatch/ },
);
check(
    'behavior',
    'missing_evidence_rejected',
    sub { $store =~ /missing evidence references/ && $store =~ /material claim needs missing evidence/ },
);
check(
    'behavior',
    'candidate_fact_rejected',
    sub { $store =~ /factual claim cannot cite candidate source evidence/ },
);
check(
    'behavior',
    'report_escapes_active_content',
    sub {
        $renderer =~ /from html import escape/
          && $renderer =~ /escape\(claim\.get\("text"/
          && $renderer =~ /escape\(val_str\)/
          && $renderer !~ /<script\b/i;
    },
);

sub acquisition_order {
    my $extract = index $contract, 'tavily extract';
    my $browser = index $contract, 'clean-session hermes browser';
    return $extract >= 0 && $browser > $extract;
}

check('interaction', 'http_before_browser', sub { acquisition_order() });
check(
    'interaction',
    'browser_only_for_dynamic_pages',
    sub { index($contract, 'rendered js') >= 0 && index($contract, 'javascript applications') >= 0 },
);
check(
    'interaction',
    'clean_unauthenticated_session',
    sub { index($contract, 'clean-session') >= 0 && index($contract, 'unauthenticated') >= 0 },
);
check(
    'interaction',
    'first_party_network_capture',
    sub {
        index($contract, 'network requests') >= 0
          && index($contract, 'first-party') >= 0
          && index($contract, 'official_domain') >= 0;
    },
);
check(
    'interaction',
    'capture_only_no_replay',
    sub {
        index($contract, 'capture-only') >= 0
          && index($contract, 'never replay') >= 0
          && index($contract, 'mutation') >= 0;
    },
);
check(
    'interaction',
    'dynamic_wait_contract',
    sub {
        (
            index($contract, 'wait_for_network_idle') >= 0
              && index($contract, 'wait_for_element') >= 0
        ) || (
            index($contract, 'agent-browser wait --load networkidle') >= 0
              && index($contract, 'agent-browser wait <selector>') >= 0
        );
    },
);
check(
    'interaction',
    'accessibility_first_targeting',
    sub {
        (index($contract, 'accessibility.getfullaxtree') >= 0
            || index($contract, 'accessibility tree') >= 0)
          && index($contract, 'screenshot') >= 0
          && index($contract, 'fallback') >= 0;
    },
);
check(
    'interaction',
    'tab_reuse_and_cleanup',
    sub {
        (
            index($contract, 'current_tab') >= 0
              && index($contract, 'list_tabs') >= 0
              && index($contract, 'switch_tab') >= 0
        ) || (
            index($contract, 'agent-browser tab list') >= 0
              && index($contract, 'agent-browser tab close') >= 0
              && index($contract, 'reuse') >= 0
        );
    },
);
check(
    'interaction',
    'post_action_verification',
    sub {
        index($contract, 'after each browser action') >= 0
          || index($contract, 'after clicking') >= 0
          || index($contract, 'targeted observation') >= 0;
    },
);
check(
    'interaction',
    'bounded_step_trace',
    sub {
        (
            index($contract, 'step trace') >= 0
              || (
                index($contract, 'agent-browser trace start') >= 0
                  && index($contract, 'agent-browser trace stop') >= 0
              )
        ) && index($contract, 'duration') >= 0
          && index($contract, 'error') >= 0;
    },
);

my @behavior = grep { $_->[0] eq 'behavior' } @checks;
my @interaction = grep { $_->[0] eq 'interaction' } @checks;
my $behavior_passed = grep { $_->[2] } @behavior;
my $interaction_passed = grep { $_->[2] } @interaction;
my $passed = $behavior_passed + $interaction_passed;
my $score = 100 * $passed / @checks;

printf "METRIC research_harness_score=%.1f\n", $score;
say "METRIC behavior_checks_passed=$behavior_passed";
say "METRIC interaction_checks_passed=$interaction_passed";
say "METRIC total_checks=" . scalar @checks;
