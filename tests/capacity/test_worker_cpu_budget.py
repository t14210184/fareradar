def test_worker_batch_and_query_budget_bounded(run_cli):
    got=run_cli('worker-budget',{'batchItems':10,'d1Statements':43,'continuationCursor':False}); assert got['allowed'] is True
    got=run_cli('worker-budget',{'batchItems':11,'d1Statements':43,'continuationCursor':True}); assert got['allowed'] is False and got['should_continue'] is True
    got=run_cli('worker-budget',{'batchItems':10,'d1Statements':51,'continuationCursor':True}); assert got['allowed'] is False
