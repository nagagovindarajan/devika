DELETE FROM agent_state;
UPDATE projects SET message_stack_json='[]' WHERE project = 'ec2-alb-apache'