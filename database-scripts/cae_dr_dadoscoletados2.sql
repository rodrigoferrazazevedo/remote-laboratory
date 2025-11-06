-- 1) plant_config
CREATE TABLE `plant_config` (
  `id`                INT           NOT NULL AUTO_INCREMENT,
  `experiment_name`   VARCHAR(100)  NOT NULL,
  `ip_profinet`       VARCHAR(12)   NOT NULL,
  `rack_profinet`     INT           NOT NULL,
  `slot_profinet`     INT           NOT NULL,
  `db_number_profinet` INT          NOT NULL,
  `num_of_inputs`     INT           NOT NULL,
  `num_of_outputs`    INT           NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_experiment_name` (`experiment_name`)
);

-- 2) dadoscoletados2
CREATE TABLE `dadoscoletados2` (
  `id`              INT            NOT NULL AUTO_INCREMENT,
  `experimentName`  VARCHAR(45)    NOT NULL,
  `experiment_id`   INT            NOT NULL,
  `step`            INT            NOT NULL,
  `pulse_train`     VARCHAR(9999)  NOT NULL,
  `pulse_value`     INT            NOT NULL,
  `timeToChange`    VARCHAR(45)    NOT NULL,
  `time_stamp`      DATETIME(3)    NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `float_value`     FLOAT          NOT NULL,
  PRIMARY KEY (`id`)
);

-- 3) dadoscoletados_summary
CREATE TABLE `dadoscoletados_summary` (
  `id`            INT           NOT NULL AUTO_INCREMENT,
  `experiment_id` INT           NOT NULL,
  `pattern`       VARCHAR(9999) NOT NULL,
  `time_stamp`    DATETIME(3)   NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`)
);


-- 3) dadoscoletados_summary
CREATE TABLE `ground_truth_patterns` (
  `id`              INT           NOT NULL AUTO_INCREMENT,
  `experiment_name`  VARCHAR(45)    NOT NULL,
  `ground_truth`         VARCHAR(9999) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_experiment_name` (`experiment_name`)
);