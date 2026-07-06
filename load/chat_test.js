// k6 load test for /chat (streaming RAG) — run: k6 run load/chat_test.js
// A 0.5B model on one consumer GPU has modest throughput: keep VUs low and
// report honest p50/p95 + tokens/s numbers.
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  insecureSkipTLSVerify: true,
  stages: [
    { duration: '30s', target: 2 },
    { duration: '2m', target: 2 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<30000'],
    http_req_failed: ['rate<0.05'],
  },
};

const BASE = __ENV.BASE_URL || 'https://localhost';

const QUESTIONS = [
  'What is machine learning?',
  'What is Kubernetes used for?',
  'What is a vector database optimized for?',
  'What was PostgreSQL originally called?',
  'What is the foundation of deep learning?',
];

export default function () {
  const q = QUESTIONS[Math.floor(Math.random() * QUESTIONS.length)];
  const res = http.post(
    `${BASE}/chat`,
    JSON.stringify({ query: q }),
    { headers: { 'Content-Type': 'application/json' }, timeout: '120s' },
  );
  check(res, {
    'status 200': (r) => r.status === 200,
    'stream finished': (r) => r.body && r.body.includes('"event": "done"'),
  });
  sleep(2);
}
