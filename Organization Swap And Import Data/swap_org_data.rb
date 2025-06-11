### Manually swap Org OHMS
source_org = 'thebremanmuseum'
destination_org = 'thebreman'

source_organization = Organization.find_by(url: source_org)
destination_organization = Organization.find_by(url: destination_org)
interviews = source_organization.interviews
interviews.each do |interview|
    interview.organization_id = destination_organization.id
    interview.save
end
organization_users = source_organization.organization_users
organization_users.each do |organization_user|
    user = OrganizationUser::where(organization_id: destination_organization.id,user_id: organization_user.user_id).try(:first)
    if user.nil?
        organization_user.organization_id = destination_organization.id
        organization_user.save
    end
end