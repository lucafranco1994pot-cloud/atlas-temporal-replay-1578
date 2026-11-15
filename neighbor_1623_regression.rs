// Regression witness supplied in temporalio/sdk-rust issue #1623.
// Run inside the existing tests module in
// crates/sdk-core/src/worker/workflow/history_update.rs.
// Source: https://github.com/temporalio/sdk-rust/issues/1623

#[rstest::rstest]
#[case::activity(EventType::ActivityTaskCompleted)]
#[case::timer(EventType::TimerFired)]
#[case::signal(EventType::WorkflowExecutionSignaled)]
fn legacy_query_does_not_deliver_inputs_before_workflow_task_started(#[case] input: EventType) {
    let mut history = TestHistoryBuilder::default();
    history.add_by_type(EventType::WorkflowExecutionStarted);
    history.add_full_wf_task();
    let mut events = history.get_full_history_info().unwrap().events().to_vec();
    events.push(HistoryEvent {
        event_id: 5,
        event_type: input as i32,
        ..Default::default()
    });
    events.push(HistoryEvent {
        event_id: 6,
        event_type: EventType::WorkflowTaskScheduled as i32,
        ..Default::default()
    });
    let (mut query, remaining) = HistoryUpdate::from_events(events, 3, 0, true);
    assert!(remaining.is_empty());
    assert_eq!(
        query
            .take_next_wft_sequence(0)
            .unwrap_events()
            .last()
            .unwrap()
            .event_id,
        3
    );
    assert_eq!(
        query
            .take_next_wft_sequence(3)
            .unwrap_events()
            .last()
            .unwrap()
            .event_id,
        4
    );
    assert_matches!(query.take_next_wft_sequence(3), NextWFT::ReplayOver);

    let mut events = history.get_full_history_info().unwrap().events().to_vec();
    events.push(HistoryEvent {
        event_id: 5,
        event_type: input as i32,
        ..Default::default()
    });
    events.push(HistoryEvent {
        event_id: 6,
        event_type: EventType::WorkflowTaskScheduled as i32,
        ..Default::default()
    });
    events.push(HistoryEvent {
        event_id: 7,
        event_type: EventType::WorkflowTaskStarted as i32,
        ..Default::default()
    });
    let (mut query, _) = HistoryUpdate::from_events(events, 3, 0, true);
    query.take_next_wft_sequence(0).unwrap_events();
    let next = query.take_next_wft_sequence(3).unwrap_events();
    assert_eq!(next.last().unwrap().event_id, 7);
    assert!(next.iter().any(|event| event.event_type() == input));
}
