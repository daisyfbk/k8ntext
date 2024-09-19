find /Users/matte/Library/CloudStorage/OneDrive-FondazioneBrunoKessler/projects/audit/results/kfoldtests_33 -name 'model*.keras' | while read model; do
    # model /Users/matte/Library/CloudStorage/OneDrive-FondazioneBrunoKessler/projects/audit/results/kfoldtests_33/40f_withbg/attempt_4/model_4.keras
    features=$(echo $model | sed -E 's/.*\/([0-9]+)f_.*/\1/')
    withbg=$(echo $model | sed -E 's/.*(nobg|withbg).*/\1/')
    attempt=$(echo $model | sed -E 's/.*attempt_([0-9]+).*/\1/')
    OUT_FOLDER="out3/${features}features_${withbg}_attempt${attempt}"
    mkdir -p $OUT_FOLDER
    CREATE_OUT_SUBFOLDERS=0 OUT_FOLDER=$OUT_FOLDER python3 model.py -m $model -f /Users/matte/RawData/audit-data/kubernetes-event-dataset/raw-audit-logs.log_apionly_cplabel
done

find /Users/matte/Library/CloudStorage/OneDrive-FondazioneBrunoKessler/projects/audit/results/zeroing -name "model*.keras" | while read model; do
    OUT_FOLDER="zeroing/originalhadname_$(dirname $model | rev | cut -d'/' -f1 | rev)"
    echo CREATE_OUT_SUBFOLDERS=0 OUT_FOLDER=$OUT_FOLDER python3 model.py -m $model -f /Users/matte/RawData/audit-data/kubernetes-event-dataset/raw-audit-logs.log_apionly_cplabel
done