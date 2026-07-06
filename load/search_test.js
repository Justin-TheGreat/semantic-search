// k6 load test for /search — run: k6 run load/search_test.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  insecureSkipTLSVerify: true, // self-signed local cert
  stages: [
    { duration: '30s', target: 10 },
    { duration: '1m', target: 10 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<1000'],
    http_req_failed: ['rate<0.01'],
  },
};

const BASE = __ENV.BASE_URL || 'https://localhost';

const QUERIES = [
  'machine learning basics',
  'container orchestration',
  'relational database',
  'vector similarity search',
  'neural network training',
  'docker containers',
];

export default function () {
  const q = QUERIES[Math.floor(Math.random() * QUERIES.length)];
  const res = http.post(
    `${BASE}/search`,
    JSON.stringify({ query: q, limit: 5 }),
    { headers: { 'Content-Type': 'application/json' } },
  );
  check(res, {
    'status 200': (r) => r.status === 200,
    'has hits': (r) => JSON.parse(r.body).hits !== undefined,
  });
  sleep(1);
}
