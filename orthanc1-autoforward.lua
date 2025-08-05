-- Auto-forward script for Orthanc1
-- Forwards all received studies to Orthanc2 via DICOMweb

function OnStableStudy(studyId, tags, metadata)
    -- Log the received study
    print('Received stable study: ' .. studyId)
    
    -- Forward to Orthanc2 via DICOMweb
    local target = 'orthanc2'
    local body = {}
    body['Resources'] = {studyId}
    body['Synchronous'] = false
    
    local response = RestApiPost('/peers/' .. target .. '/store', DumpJson(body, true))
    print('Forwarded study ' .. studyId .. ' to ' .. target)
end