import http.k6 from 'k6/http';
import { check, sleep } from 'k6';

// k6 Load Configuration
// Target traffic: default 30 RPS across virtual users
export const options = {
  scenarios: {
    constant_request_rate: {
      executor: 'constant-arrival-rate',
      rate: __ENV.RPS_TARGET ? parseInt(__ENV.RPS_TARGET) : 30,
      timeUnit: '1s',
      duration: __ENV.DURATION ? __ENV.DURATION : '45s',
      preAllocatedVUs: __ENV.VUS ? parseInt(__ENV.VUS) : 10,
      maxVUs: 50,
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.50'], // For load tracking
  },
};

const BASE_URL = __ENV.TARGET_URL || 'http://frontend-service:8000';

export default function () {
  const payload = JSON.stringify({
    item_id: 'item_k6_load',
    quantity: 1,
    amount: 50.0,
    user_id: `user_${__VU}_${__ITER}`,
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
    },
    timeout: '6s',
  };

  const res = http.post(`${BASE_URL}/orders`, payload, params);

  check(res, {
    'status is 200': (r) => r.status === 200,
  });

  sleep(0.1);
}
