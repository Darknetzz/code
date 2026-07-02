use crate::models::{PingReply, ProbeStats};

pub fn compute_stats(sent: u32, replies: &[PingReply]) -> ProbeStats {
    let successful: Vec<f64> = replies
        .iter()
        .filter(|reply| !reply.timed_out)
        .map(|reply| reply.rtt_ms)
        .collect();
    let received = successful.len() as u32;
    let loss = if sent == 0 {
        0.0
    } else {
        100.0 * (1.0 - f64::from(received) / f64::from(sent))
    };

    if successful.is_empty() {
        return ProbeStats {
            packets_sent: sent,
            packets_received: 0,
            packet_loss_pct: loss,
            min_ms: None,
            avg_ms: None,
            max_ms: None,
            stddev_ms: None,
            jitter_ms: None,
        };
    }

    let min_ms = successful.iter().copied().fold(f64::INFINITY, f64::min);
    let max_ms = successful.iter().copied().fold(f64::NEG_INFINITY, f64::max);
    let avg_ms = successful.iter().sum::<f64>() / successful.len() as f64;
    let variance = successful
        .iter()
        .map(|value| {
            let diff = value - avg_ms;
            diff * diff
        })
        .sum::<f64>()
        / successful.len() as f64;
    let stddev_ms = variance.sqrt();
    let jitter_ms = successful
        .iter()
        .map(|value| (value - avg_ms).abs())
        .sum::<f64>()
        / successful.len() as f64;

    ProbeStats {
        packets_sent: sent,
        packets_received: received,
        packet_loss_pct: loss,
        min_ms: Some(min_ms),
        avg_ms: Some(avg_ms),
        max_ms: Some(max_ms),
        stddev_ms: Some(stddev_ms),
        jitter_ms: Some(jitter_ms),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn computes_stats_for_replies() {
        let replies = vec![
            PingReply {
                seq: 1,
                rtt_ms: 10.0,
                ttl: Some(56),
                timed_out: false,
            },
            PingReply {
                seq: 2,
                rtt_ms: 20.0,
                ttl: Some(56),
                timed_out: false,
            },
            PingReply {
                seq: 3,
                rtt_ms: 0.0,
                ttl: None,
                timed_out: true,
            },
        ];
        let stats = compute_stats(3, &replies);
        assert_eq!(stats.packets_sent, 3);
        assert_eq!(stats.packets_received, 2);
        assert!((stats.packet_loss_pct - 33.333333).abs() < 0.01);
        assert_eq!(stats.min_ms, Some(10.0));
        assert_eq!(stats.max_ms, Some(20.0));
        assert_eq!(stats.avg_ms, Some(15.0));
    }

    #[test]
    fn all_timeouts_yield_no_rtt_stats() {
        let replies = vec![PingReply {
            seq: 1,
            rtt_ms: 0.0,
            ttl: None,
            timed_out: true,
        }];
        let stats = compute_stats(1, &replies);
        assert_eq!(stats.packets_received, 0);
        assert_eq!(stats.min_ms, None);
        assert_eq!(stats.packet_loss_pct, 100.0);
    }
}
