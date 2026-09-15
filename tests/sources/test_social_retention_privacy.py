def test_private_notification_raw_body_not_retained(run_cli):
    got=run_cli('social-retention',{'privacy_class':'PRIVATE_NOTIFICATION','raw_body':'private text','content_sha256':'a'*64}); assert got['raw_body'] is None
    got=run_cli('social-retention',{'privacy_class':'PUBLIC','raw_body':'public text','content_sha256':'a'*64}); assert got['raw_body']=='public text'
