for id in {99..100}
do
    echo "Starting multi-agent experiment : $id"
    python expe_setup.py --exp_id $id --communication 1
done
for id in {90..100}
do
    echo "Starting solo-agent experiment : $id"
    python expe_setup.py --exp_id $id --communication 0
done
