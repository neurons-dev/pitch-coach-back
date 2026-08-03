package com.pitchcoach.core.session.infrastructure;

import com.pitchcoach.core.common.exception.AnalysisServiceException;
import com.pitchcoach.core.session.infrastructure.dto.AnalysisJobCreateRequest;
import com.pitchcoach.core.session.infrastructure.dto.AnalysisJobCreateResponse;
import com.pitchcoach.core.session.infrastructure.dto.AnalysisJobStatusResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.net.http.HttpClient;
import java.time.Duration;
import java.util.UUID;

@Component
public class AnalysisServiceClient {

    private final RestClient restClient;
    private final String internalToken;

    public AnalysisServiceClient(
            @Value("${analysis-service.base-url}") String baseUrl,
            @Value("${analysis-service.internal-token}") String internalToken,
            @Value("${analysis-service.connect-timeout-ms:3000}") long connectTimeoutMs,
            @Value("${analysis-service.read-timeout-ms:10000}") long readTimeoutMs
    ) {
        // uvicorn은 HTTP/1.1만 지원하는데, JDK HttpClient는 평문 HTTP에서도 h2c 업그레이드를
        // 시도해 요청이 깨지는 문제가 있어 HTTP/1.1로 고정한다.
        HttpClient httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(Duration.ofMillis(connectTimeoutMs))
                .build();
        JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory(httpClient);
        requestFactory.setReadTimeout(Duration.ofMillis(readTimeoutMs));

        this.restClient = RestClient.builder()
                .baseUrl(baseUrl)
                .requestFactory(requestFactory)
                .build();
        this.internalToken = internalToken;
    }

    public AnalysisJobCreateResponse createJob(AnalysisJobCreateRequest request, String idempotencyKey) {
        try {
            return restClient.post()
                    .uri("/internal/v1/analysis-jobs")
                    .contentType(MediaType.APPLICATION_JSON)
                    .header("X-Internal-Token", internalToken)
                    .header("Idempotency-Key", idempotencyKey)
                    .body(request)
                    .retrieve()
                    .body(AnalysisJobCreateResponse.class);
        } catch (RestClientException e) {
            throw new AnalysisServiceException(e);
        }
    }

    public AnalysisJobStatusResponse getJobStatus(UUID analysisJobId) {
        try {
            return restClient.get()
                    .uri("/internal/v1/analysis-jobs/{id}", analysisJobId)
                    .header("X-Internal-Token", internalToken)
                    .retrieve()
                    .body(AnalysisJobStatusResponse.class);
        } catch (RestClientException e) {
            throw new AnalysisServiceException(e);
        }
    }
}
