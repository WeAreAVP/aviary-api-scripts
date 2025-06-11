### Manually convert the OHMS Records to Aviary Resources
org_url = "testneworg"
if org_url == "testneworg"
    collection_id = 67
end

org_url = "nunncentertest1"
organization = Organization.find_by(url: org_url)
interviews = organization.interviews

org_url = "globalhealthchronicles"
organization = Organization.find_by(url: org_url)
interviews = organization.interviews


failed_ids = []
total = interviews.count
count = 0
interviews.each do |interview|
    collection_id = 0
    if interview.collection_name.include?('The Early Years of AIDS')
        collection_id = 2847
    elsif interview.collection_name.include?('Polio')
        collection_id = 2846
    elsif interview.collection_name.include?('COVID-19')
        collection_id = 2849
    elsif interview.collection_name.include?('Smallpox')
        collection_id = 2844
    elsif interview.collection_name.include?('Ebola')
        collection_id = 2848
    end
    if collection_id.positive?
        export_text = Aviary::ExportOhmsInterviewXML.new.export(interview)
        import = Import.create(organization_id: organization.id, collection_id: collection_id,
            import_type: 1, user_id: organization.user.id, title: interview.title,
            status: Import::StatusType::IN_PROGRESS,
            sync_info: { 'title' => interview.title, 'is_featured' => "false".to_sym,
                        'access' => 1, 'interview_id' => interview.id })
        file = Tempfile.new(["content#{Time.now.to_i}", '.xml'])
        file.write(export_text.to_xml)
        file.rewind

        import.import_files.create(associated_file: File.open(file.path), file_type: ImportFile::FileType::XML,
                                permission_object: {}.to_json)

        file.close

        BulkImportWorker.new.perform(import.id)
        import.reload

        collection_resource_id = CollectionResource.where(external_resource_id: interview.id,
                                                            external_type: 'ohms_interview').try(:first).try(:id)
        if collection_resource_id.present?
            resource =  CollectionResource.where(external_resource_id: interview.id,
                external_type: 'ohms_interview').try(:first)
            
            file_name = interview.id.to_s + '_' + interview.title.gsub(/[^A-Za-z0-9 ]+/, '').strip.downcase.tr(' ', '_').delete('.')

            s3 = Aws::S3::Client.new(
                access_key_id: 'AKIAR6PLJPXVS3ZRI2XQ',
                secret_access_key: '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',
                region: 'us-east-1'
            )
            bucket_name = 'aviaryplatform-local'
            object_path = "Interviews/"+file_name
            expiry = 3600
            if interview.media_host == "YouTube"
                begin
                    s3.head_object(bucket: bucket_name, key: object_path+'.mp4')

                    url = Aws::S3::Object.new(key: object_path+'.mp4', bucket_name: bucket_name, client: s3)
                            .presigned_url(:get, expires_in: expiry.ceil, response_content_disposition: 'attachment;',
                                                    response_content_type: 'mp4')
                    media = resource.collection_resource_files.first
                    media.update(resource_file: URI.open(url),embed_code: '', embed_type: '',resource_file_file_name: file_name+'.mp4', file_display_name: interview.title)
                    media.resource_file_file_name = file_name
                    media.save
                rescue Aws::S3::Errors::NotFound

                end
            end

            if interview.media_host == "SoundCloud"
                begin
                    s3.head_object(bucket: bucket_name, key: object_path+'.mp3')

                    url = Aws::S3::Object.new(key: object_path+'.mp3', bucket_name: bucket_name, client: s3)
                            .presigned_url(:get, expires_in: expiry.ceil, response_content_disposition: 'attachment;',
                                                    response_content_type: 'mp3')
                    collection_resource_file = resource.collection_resource_files.create(resource_file: URI.open(url), embed_code: '', embed_type: '',
                        target_domain: '', resource_file_file_name: file_name+'.mp3', file_display_name: interview.title,
                        access: 1,
                        embed_content_type: "", sort_order: 1,
                    )
                    ohms_files = import.import_files
                    aviary_hash = []
                    ohms_file = Aviary::BulkImportManager::OHMSFile.new
                    ohms_files.each do |single_file|
                        aviary_hash << ohms_file.process_file(single_file, import)
                    end

                    resources = aviary_hash
                    resources.each_with_index do |resource, _index|
                        collection_resource =  Aviary::ResourceManager.new.create_resource_and_description(resource, import)
                        if resource[:index].present?
                            Aviary::ResourceManager.new.process_file_index(import, resource, collection_resource_file)
                        end
                        if resource[:transcript].present?
                            Aviary::ResourceManager.new.process_file_transcript(import, resource, collection_resource_file)
                        end
                    end
                    collection_resource_file.resource_file_file_name = file_name
                    collection_resource_file.save
                rescue Aws::S3::Errors::NotFound

                end
            end
            puts "Interview ID: #{interview.id} Created ===> #{count+1} of #{total}"
            count = count + 1
        else
            failed_ids[] << interview.id
        end
    else
        failed_ids[] << interview.id
    end
    puts failed_ids
end


# interview = Interviews::Interview.find(collection_resource.external_resource_id)


org_url = "globalhealthchronicles"
organization = Organization.find_by(url: org_url)
interviews = organization.interviews
failed_ids = []
total = interviews.count
count = 0
interviews.each do |interview|
    begin
    collection_resource = CollectionResource.where(external_resource_id: interview.id,
        external_type: 'ohms_interview').try(:first)
    if collection_resource.collection_resource_files.count.zero?
        file_name = interview.id.to_s + '_' + interview.title.gsub(/[^A-Za-z0-9 ]+/, '').strip.downcase.tr(' ', '_').delete('.')
        s3 = Aws::S3::Client.new(
            access_key_id: 'AKIAR6PLJPXVS3ZRI2XQ',
            secret_access_key: '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',
            region: 'us-east-1'
        )
        bucket_name = 'aviaryplatform-local'
        object_path = "Interviews/"+file_name
        expiry = 3600
        if interview.media_host == "SoundCloud"
            begin
                s3.head_object(bucket: bucket_name, key: object_path+'.mp3')

                url = Aws::S3::Object.new(key: object_path+'.mp3', bucket_name: bucket_name, client: s3)
                        .presigned_url(:get, expires_in: expiry.ceil, response_content_disposition: 'attachment;',
                                                response_content_type: 'mp3')
                collection_resource_file = collection_resource.collection_resource_files.create(resource_file: URI.open(url), embed_code: '', embed_type: '',
                    target_domain: '', resource_file_file_name: file_name+'.mp3', file_display_name: interview.title,
                    access: 1,
                    embed_content_type: "", sort_order: 1,
                )
                collection_resource_file.resource_file_file_name = file_name
                collection_resource_file.save
            rescue Aws::S3::Errors::NotFound

            end
            export_text = Aviary::ExportOhmsInterviewXML.new.export(interview)
            import = Import.create(organization_id: organization.id, collection_id: collection_resource.collection_id,
                import_type: 1, user_id: organization.user.id, title: interview.title,
                status: Import::StatusType::IN_PROGRESS,
                sync_info: { 'title' => interview.title, 'is_featured' => "false".to_sym,
                            'access' => 1, 'interview_id' => interview.id })
            file = Tempfile.new(["content#{Time.now.to_i}", '.xml'])
            file.write(export_text.to_xml)
            file.rewind

            import.import_files.create(associated_file: File.open(file.path), file_type: ImportFile::FileType::XML,
                                    permission_object: {}.to_json)

            file.close
            ohms_files = import.import_files
            aviary_hash = []
            ohms_file = Aviary::BulkImportManager::OHMSFile.new
            ohms_files.each do |single_file|
                aviary_hash << ohms_file.process_file(single_file, import)
            end

            resources = aviary_hash
            resources.each_with_index do |resource, _index|
                collection_resource =  Aviary::ResourceManager.new.create_resource_and_description(resource, import)
                if resource[:index].present?
                    Aviary::ResourceManager.new.process_file_index(import, resource, collection_resource_file)
                end
                if resource[:transcript].present?
                    Aviary::ResourceManager.new.process_file_transcript(import, resource, collection_resource_file)
                end
            end
        end
    end
    puts "Interview ID: #{interview.id} Created ===> #{count+1} of #{total}"
    count = count + 1
    rescue Aws::S3::Errors::NotFound
        failed_ids << collection_resource.id
    end
end






org_url = "globalhealthchronicles"
organization = Organization.find_by(url: org_url)
interviews = organization.interviews
counts = 0
failed_ids = []
total = interviews.count
count = 0
interviews.each do |interview|
    if interview.collection_name.include?('COVID-19')
        collection_id = 2849
        puts interview.media_host
        export_text = Aviary::ExportOhmsInterviewXML.new.export(interview)
        import = Import.create(organization_id: organization.id, collection_id: collection_id,
            import_type: 1, user_id: organization.user.id, title: interview.title,
            status: Import::StatusType::IN_PROGRESS,
            sync_info: { 'title' => interview.title, 'is_featured' => "false".to_sym,
                        'access' => 1, 'interview_id' => interview.id })
        file = Tempfile.new(["content#{Time.now.to_i}", '.xml'])
        file.write(export_text.to_xml)
        file.rewind

        import.import_files.create(associated_file: File.open(file.path), file_type: ImportFile::FileType::XML,
                                permission_object: {}.to_json)

        file.close

        BulkImportWorker.new.perform(import.id)
        import.reload

        collection_resource_id = CollectionResource.where(external_resource_id: interview.id,
                                                            external_type: 'ohms_interview').try(:first).try(:id)
        if collection_resource_id.present?
            resource =  CollectionResource.where(external_resource_id: interview.id,
                external_type: 'ohms_interview').try(:first)
            
            file_name = interview.id.to_s + '_' + interview.title.gsub(/[^A-Za-z0-9 ]+/, '').strip.downcase.tr(' ', '_').delete('.')

            s3 = Aws::S3::Client.new(
                access_key_id: 'AKIAR6PLJPXVS3ZRI2XQ',
                secret_access_key: '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',
                region: 'us-east-1'
            )
            bucket_name = 'aviaryplatform-local'
            object_path = "Interviews/"+file_name
            expiry = 3600
            if interview.media_host == "SoundCloud"
                begin
                    s3.head_object(bucket: bucket_name, key: object_path+'.mp3')

                    url = Aws::S3::Object.new(key: object_path+'.mp3', bucket_name: bucket_name, client: s3)
                            .presigned_url(:get, expires_in: expiry.ceil, response_content_disposition: 'attachment;',
                                                    response_content_type: 'mp3')
                    collection_resource_file = resource.collection_resource_files.create(resource_file: URI.open(url), embed_code: '', embed_type: '',
                        target_domain: '', resource_file_file_name: file_name+'.mp3', file_display_name: interview.title,
                        access: 1,
                        embed_content_type: "", sort_order: 1,
                    )
                    ohms_files = import.import_files
                    aviary_hash = []
                    ohms_file = Aviary::BulkImportManager::OHMSFile.new
                    ohms_files.each do |single_file|
                        aviary_hash << ohms_file.process_file(single_file, import)
                    end

                    resources = aviary_hash
                    resources.each_with_index do |resource, _index|
                        collection_resource =  Aviary::ResourceManager.new.create_resource_and_description(resource, import)
                        if resource[:index].present?
                            Aviary::ResourceManager.new.process_file_index(import, resource, collection_resource_file)
                        end
                        if resource[:transcript].present?
                            Aviary::ResourceManager.new.process_file_transcript(import, resource, collection_resource_file)
                        end
                    end
                    collection_resource_file.resource_file_file_name = file_name
                    collection_resource_file.save
                rescue Aws::S3::Errors::NotFound

                end
            end
            puts "Interview ID: #{interview.id} Created ===> #{count+1} of #{total}"
            count = count + 1
            counts = counts + 1
        end
    end
               
end
puts counts