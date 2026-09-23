-- ai_model_master: tracks trained models
CREATE TABLE IF NOT EXISTS ai_model_master (
    model_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name      VARCHAR(255) NOT NULL,
    model_type      VARCHAR(100) NOT NULL,
    algorithm       VARCHAR(100) NOT NULL,
    version         VARCHAR(50) NOT NULL,
    training_date   TIMESTAMP NOT NULL DEFAULT now()
);

-- anomaly_detection_result: stores anomaly scores and predictions for events
CREATE TABLE IF NOT EXISTS anomaly_detection_result (
    detection_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id        UUID NOT NULL, -- references network_event
    model_id        UUID NOT NULL REFERENCES ai_model_master(model_id),
    anomaly_score   FLOAT NOT NULL,
    prediction      VARCHAR(50) NOT NULL,
    detection_time  TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_anomaly_detection_event ON anomaly_detection_result(event_id);
CREATE INDEX IF NOT EXISTS idx_anomaly_detection_model ON anomaly_detection_result(model_id);
