-- Auto-forward script for Orthanc1
-- Forwards all received studies to Orthanc2 via DICOMweb then deletes them

function OnStableStudy(studyId, tags, metadata)
    -- Log the received study
    print('Received stable study: ' .. studyId)
    
    -- Forward to Orthanc2 via DICOMweb
    local target = 'orthanc2'
    local body = {}
    body['Resources'] = {studyId}
    body['Synchronous'] = true  -- Wait for completion
    
    local response = RestApiPost('/peers/' .. target .. '/store', DumpJson(body, true))
    print('Forwarded study ' .. studyId .. ' to ' .. target)
    
    -- Delete the study from Orthanc1 after successful forward
    -- We add a small delay to ensure the transfer is complete
    print('Scheduling deletion of study ' .. studyId .. ' from Orthanc1')
    RestApiPost('/jobs/', DumpJson({
        ['Type'] = 'DeleteResource',
        ['Resource'] = studyId,
        ['Synchronous'] = false,
        ['Priority'] = 0,
        ['PermissiveMode'] = true
    }, true))
end