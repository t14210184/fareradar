def test_same_promotion_fingerprint_across_channels(run_cli):
    a={'market':'TW','airline':'IT','routes':['TPE-KIX','KHH-KIX'],'sale_start':'2026-09-16','travel_start':'2026-10-01','promo_code':'SALE'}
    b=dict(a); b['routes']=['KHH-KIX','TPE-KIX']
    assert run_cli('promo-fingerprint',a)==run_cli('promo-fingerprint',b)


def test_eligibility_requirements_are_part_of_promotion_identity(run_cli):
    public={'market':'TW','airline':'IT','routes':['TPE-KIX'],'sale_start':'2026-09-16','travel_start':'2026-10-01','promo_code':None,'member_requirement':None,'channel_requirement':None}
    member=dict(public); member['member_requirement']='TEAM_TIGER'
    app=dict(public); app['channel_requirement']='APP_ONLY'
    assert run_cli('promo-fingerprint',public) != run_cli('promo-fingerprint',member)
    assert run_cli('promo-fingerprint',public) != run_cli('promo-fingerprint',app)
    same_member=dict(member); same_member['routes']=['TPE-KIX']
    assert run_cli('promo-fingerprint',member) == run_cli('promo-fingerprint',same_member)

def test_material_promo_rule_changes_do_not_collapse(run_cli):
    base={'market':'TW','airline':'MM','routes':['TPE-KIX'],'sale_start':'2026-09-15','sale_end':'2026-09-30','travel_start':'2026-11-01','travel_end':'2026-11-30','eligible_weekdays':[2,3,4],'blackout_dates':['2026-11-20']}
    changed=dict(base); changed['blackout_dates']=['2026-11-21']
    assert run_cli('promo-fingerprint',base) != run_cli('promo-fingerprint',changed)
    changed=dict(base); changed['travel_end']='2026-12-15'
    assert run_cli('promo-fingerprint',base) != run_cli('promo-fingerprint',changed)
